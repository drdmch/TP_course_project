import argparse
import json
import sys

from . import __version__
from .analysis import find_variables
from .ast import format_tree, to_dict
from .diagnostics import SiplSyntaxError
from .interpreter import DEFAULT_MAX_STEPS, execute
from .parser import parse

EXIT_OK = 0
EXIT_SYNTAX_ERROR = 1
EXIT_USAGE = 2
EXIT_RUNTIME_ERROR = 3
EXIT_STEP_LIMIT = 4


def make_arg_parser():
    p = argparse.ArgumentParser(prog="sipl", description="SIPL language tools")
    p.add_argument("--version", action="version", version="sipl " + __version__)
    commands = p.add_subparsers(dest="command", required=True)

    cmd = commands.add_parser("parse", help="print the AST")
    cmd.add_argument("file")
    cmd.add_argument("--json", action="store_true", help="JSON output")
    cmd.add_argument("--spans", action="store_true", help="show source positions")

    cmd = commands.add_parser("check", help="check syntax")
    cmd.add_argument("file")
    cmd.add_argument("--json", action="store_true", help="JSON output")

    for name, help_text in [("run", "run a program"), ("trace", "run and print the trace")]:
        cmd = commands.add_parser(name, help=help_text)
        cmd.add_argument("file")
        cmd.add_argument("--json", action="store_true", help="JSON output")
        cmd.add_argument("-s", "--set", action="append", default=[], metavar="X=N",
                         help="initial value of a variable")
        cmd.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                         help="step limit")
    return p


def parse_set_options(items):
    state = {}
    for item in items:
        if "=" not in item:
            return None, f"bad --set value '{item}', expected X=N"
        name, value = item.split("=", 1)
        name = name.strip()
        if not name.isidentifier():
            return None, f"bad variable name '{name}'"
        try:
            state[name] = int(value)
        except ValueError:
            return None, f"'{value}' is not an integer"
    return state, None


def format_state(state):
    if not state:
        return "(empty)"
    parts = []
    for name in sorted(state):
        parts.append(f"{name} = {state[name]}")
    return ", ".join(parts)


def print_json(command, file, ok, diagnostics, **extra):
    data = {"schema": "sipl-cli/1", "command": command, "file": file, "ok": ok,
            "diagnostics": diagnostics}
    data.update(extra)
    print(json.dumps(data, ensure_ascii=False, indent=2))


def usage_error(args, message):
    if args.json:
        diag = {"severity": "error", "code": "cli.usage", "message": message, "span": None}
        print_json(args.command, args.file, False, [diag])
    else:
        print("sipl: error: " + message, file=sys.stderr)
    return EXIT_USAGE


def trace_line(event):
    seq = f"{event['seq']:>4}"
    kind = event["kind"]
    if kind == "program_started":
        return f"{seq}  start     {format_state(event['state'])}"
    if kind == "before_statement":
        span = event["node"]["span"]
        pos = f"{span['line']}:{span['column']}"
        return f"{seq}  {pos:<8}  {event['node']['text']}"
    if kind == "variable_changed":
        old = "⊥" if event["old"] is None else event["old"]
        return f"{seq}              {event['name']}: {old} → {event['new']}"
    if kind == "condition_evaluated":
        value = "true" if event["value"] else "false"
        text = f"{seq}              {event['node']['text']} = {value}"
        if event["iteration"] is not None:
            text += f"  (#{event['iteration'] + 1})"
        return text
    if kind == "program_finished":
        return (f"{seq}  end ({event['status']}), {event['steps']} steps: "
                f"{format_state(event['state'])}")
    return None


def main(argv=None):
    args = make_arg_parser().parse_args(argv)

    try:
        with open(args.file, encoding="utf-8") as f:
            source = f.read()
    except OSError:
        return usage_error(args, f"cannot read file '{args.file}'")

    try:
        program = parse(source)
    except SiplSyntaxError as e:
        if args.json:
            print_json(args.command, args.file, False, [e.diagnostic.to_dict()])
        else:
            print(e.diagnostic.format(source, args.file), file=sys.stderr)
        return EXIT_SYNTAX_ERROR

    if args.command == "parse":
        if args.json:
            print_json("parse", args.file, True, [], ast=to_dict(program))
        else:
            print(format_tree(program, with_spans=args.spans))
        return EXIT_OK

    if args.command == "check":
        variables = find_variables(program)
        if args.json:
            print_json("check", args.file, True, [], variables=variables)
        else:
            print(f"{args.file}: OK")
            print("inputs:   " + (", ".join(variables["inputs"]) or "-"))
            print("assigned: " + (", ".join(variables["assigned"]) or "-"))
        return EXIT_OK

    state, error = parse_set_options(args.set)
    if error:
        return usage_error(args, error)
    if args.max_steps < 1:
        return usage_error(args, "--max-steps must be positive")

    result = execute(program, state, args.max_steps)
    if result["status"] == "ok":
        code = EXIT_OK
    elif result["status"] == "step_limit":
        code = EXIT_STEP_LIMIT
    else:
        code = EXIT_RUNTIME_ERROR

    if args.json:
        diagnostics = []
        if result["diagnostic"] is not None:
            diagnostics.append(result["diagnostic"])
        extra = {"input": state,
                 "result": {"status": result["status"], "steps": result["steps"],
                            "state": result["state"], "diagnostic": result["diagnostic"]}}
        if args.command == "trace":
            extra["events"] = result["events"]
        print_json(args.command, args.file, code == EXIT_OK, diagnostics, **extra)
        return code

    if args.command == "trace":
        for event in result["events"]:
            line = trace_line(event)
            if line is not None:
                print(line)
    elif code == EXIT_OK:
        print(format_state(result["state"]))
    else:
        print("stopped at: " + format_state(result["state"]))

    if result["diagnostic"] is not None:
        d = result["diagnostic"]
        span = d["span"]
        print(f"{args.file}:{span['line']}:{span['column']}: error: {d['message']}",
              file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
