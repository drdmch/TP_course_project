import json
import subprocess
import sys

import pytest

from sipl import parse
from sipl.analysis import find_variables
from sipl.cli import main
from conftest import example_path

POWER = example_path("valid", "power.sipl")
GCD = example_path("valid", "gcd.sipl")
BAD = example_path("invalid", "trailing_semicolon.sipl")


def run_cli(capsys, *args):
    code = main(list(args))
    out, err = capsys.readouterr()
    return code, out, err


def run_cli_json(capsys, *args):
    code, out, err = run_cli(capsys, *args, "--json")
    data = json.loads(out)
    assert data["schema"] == "sipl-cli/1"
    return code, data


def test_parse(capsys):
    code, out, err = run_cli(capsys, "parse", POWER)
    assert code == 0
    assert out.startswith("Program\n  Seq\n    Assign R")


def test_parse_spans(capsys):
    code, out, err = run_cli(capsys, "parse", POWER, "--spans")
    assert "Assign R  [3:3-3:9]" in out


def test_parse_json(capsys):
    code, data = run_cli_json(capsys, "parse", POWER)
    assert code == 0
    assert data["ok"] is True
    assert data["ast"]["type"] == "Program"


def test_check(capsys):
    code, out, err = run_cli(capsys, "check", GCD)
    assert code == 0
    assert out.startswith(GCD + ": OK")
    assert "inputs:   X, Y" in out


def test_check_json(capsys):
    code, data = run_cli_json(capsys, "check", POWER)
    assert data["variables"] == {"inputs": ["X", "Y"], "assigned": ["R", "Y"]}


def test_syntax_error(capsys):
    code, out, err = run_cli(capsys, "check", BAD)
    assert code == 1
    assert "trailing_semicolon.sipl:5:1: error" in err


def test_syntax_error_json(capsys):
    code, data = run_cli_json(capsys, "run", BAD)
    assert code == 1
    assert data["ok"] is False
    assert data["diagnostics"][0]["span"]["line"] == 5


def test_run(capsys):
    code, out, err = run_cli(capsys, "run", POWER, "--set", "X=3", "-s", "Y=4")
    assert code == 0
    assert out.strip() == "R = 81, X = 3, Y = 0"


def test_run_json(capsys):
    code, data = run_cli_json(capsys, "run", POWER, "-s", "X=2", "-s", "Y=3")
    assert code == 0
    assert data["input"] == {"X": 2, "Y": 3}
    assert data["result"]["state"] == {"X": 2, "Y": 0, "R": 8}
    assert data["result"]["steps"] == 11


def test_runtime_error(capsys):
    code, out, err = run_cli(capsys, "run", POWER, "-s", "Y=2")
    assert code == 3
    assert "stopped at: R = 1, Y = 2" in out
    assert "Variable 'X' is undefined" in err


def test_step_limit(tmp_path, capsys):
    path = tmp_path / "loop.sipl"
    path.write_text("begin while 1 = 1 do skip end", encoding="utf-8")
    code, data = run_cli_json(capsys, "run", str(path), "--max-steps", "50")
    assert code == 4
    assert data["result"]["status"] == "step_limit"


def test_trace(capsys):
    code, out, err = run_cli(capsys, "trace", POWER, "-s", "X=2", "-s", "Y=1")
    assert code == 0
    assert "R: ⊥ → 1" in out
    assert "Y > 0 = true" in out
    assert "end (ok)" in out


def test_trace_json(capsys):
    code, data = run_cli_json(capsys, "trace", POWER, "-s", "X=2", "-s", "Y=1")
    assert data["events"][0]["kind"] == "program_started"
    assert data["events"][-1]["kind"] == "program_finished"


@pytest.mark.parametrize("args", [
    ["run", POWER, "--set", "X=abc"],
    ["run", POWER, "--set", "oops"],
    ["run", POWER, "--set", "1X=2"],
    ["run", POWER, "--max-steps", "0"],
    ["check", "no_such_file.sipl"],
])
def test_usage_errors(capsys, args):
    code, out, err = run_cli(capsys, *args)
    assert code == 2
    assert err.startswith("sipl: error:")


def test_usage_error_json(capsys):
    code, data = run_cli_json(capsys, "check", "no_such_file.sipl")
    assert code == 2
    assert data["diagnostics"][0]["code"] == "cli.usage"


def test_python_m_sipl():
    proc = subprocess.run([sys.executable, "-m", "sipl", "run", POWER, "-s", "X=2", "-s", "Y=5"],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0
    assert "R = 32" in proc.stdout


def test_find_variables():
    program = parse("begin Y := X; while N > 0 do begin S := S + N; N := N - 1 end end")
    assert find_variables(program) == {"inputs": ["N", "S", "X"], "assigned": ["N", "S", "Y"]}
