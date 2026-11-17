import json

import pytest

from sipl import SiplRuntimeError, parse
from sipl.interpreter import Interpreter, eval_aexp, eval_bexp, execute, run
from conftest import read_example


def run_example(name, state):
    return run(parse(read_example("valid", name + ".sipl")), state)


def run_text(body, state=None):
    return run(parse("begin " + body + " end"), state)


@pytest.mark.parametrize("name, state, var, expected", [
    ("power", {"X": 5, "Y": 2}, "R", 25),
    ("power", {"X": 7, "Y": 0}, "R", 1),
    ("factorial", {"N": 5}, "F", 120),
    ("gcd", {"X": 12, "Y": 18}, "G", 6),
    ("log2", {"N": 1000}, "L", 9),
    ("double_factorial", {"N": 3}, "R", 48),
    ("progression_sum", {"N": 4}, "S", 20),
    ("max", {"X": 3, "Y": 9}, "M", 9),
    ("abs", {"X": -7}, "A", 7),
    ("mod_parity", {"N": 10}, "E", 1),
    ("ascii_logic", {"X": 100}, "Ok", 1),
    ("nested_blocks", {}, "X", -3),
])
def test_examples(name, state, var, expected):
    assert run_example(name, state)[var] == expected


def test_assign_and_sequence():
    assert run_text("X := 1; Y := X + 1; X := Y * 10") == {"X": 20, "Y": 2}


def test_if():
    assert run_text("if X > 0 then R := 1 else R := 2", {"X": 5})["R"] == 1
    assert run_text("if X > 0 then R := 1 else R := 2", {"X": 0})["R"] == 2


def test_while_zero_times():
    assert run_text("while X > 0 do X := X - 1", {"X": 0}) == {"X": 0}


def test_skip():
    assert run_text("skip", {"A": 1}) == {"A": 1}


def test_input_state_not_changed():
    state = {"X": 1}
    run_text("X := 2", state)
    assert state == {"X": 1}


def expr(text):
    return parse("begin X := " + text + " end").body.expr


def cond(text):
    return parse("begin while " + text + " do skip end").body.cond


def test_arithmetic():
    assert eval_aexp(expr("2 + 3 * 4"), {}) == 14
    assert eval_aexp(expr("10 - 3 - 2"), {}) == 5
    assert eval_aexp(expr("7 div 2"), {}) == 3
    assert eval_aexp(expr("7 mod 2"), {}) == 1
    assert eval_aexp(expr("-7 div 2"), {}) == -4


def test_conditions():
    assert eval_bexp(cond("1 = 1"), {}) is True
    assert eval_bexp(cond("1 > 1"), {}) is False
    assert eval_bexp(cond("¬ 1 = 1"), {}) is False
    assert eval_bexp(cond("1 = 2 ∨ 2 = 2"), {}) is True


def test_or_evaluates_both_parts():
    with pytest.raises(SiplRuntimeError):
        eval_bexp(cond("1 = 1 ∨ Z > 0"), {})


def test_undefined_variable():
    with pytest.raises(SiplRuntimeError) as info:
        run(parse("begin\n  R := X + 1\nend"))
    d = info.value.diagnostic
    assert d.code == "runtime.undefined-variable"
    assert d.span.line == 2
    assert d.span.column == 8


def test_division_by_zero():
    with pytest.raises(SiplRuntimeError) as info:
        run_text("X := 1 div 0")
    assert info.value.diagnostic.code == "runtime.division-by-zero"


def test_infinite_loop():
    with pytest.raises(SiplRuntimeError) as info:
        run(parse("begin while 1 = 1 do skip end"), max_steps=1000)
    assert info.value.diagnostic.code == "runtime.step-limit"


def test_step_limit():
    program = parse("begin X := 1; X := 2; X := 3 end")
    assert execute(program, max_steps=3)["status"] == "ok"
    result = execute(program, max_steps=2)
    assert result["status"] == "step_limit"
    assert result["steps"] == 2
    assert result["state"] == {"X": 2}


def test_bad_max_steps():
    with pytest.raises(ValueError):
        Interpreter(max_steps=0)


def power_trace(x, y):
    program = parse(read_example("valid", "power.sipl"))
    return execute(program, {"X": x, "Y": y})["events"]


def test_trace_kinds():
    kinds = [e["kind"] for e in power_trace(2, 1)]
    assert kinds == [
        "program_started",
        "before_statement", "variable_changed", "after_statement",
        "before_statement",
        "condition_evaluated",
        "before_statement", "variable_changed", "after_statement",
        "before_statement", "variable_changed", "after_statement",
        "condition_evaluated",
        "after_statement",
        "program_finished",
    ]


def test_trace_numbers():
    events = power_trace(2, 2)
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))


def test_trace_variable_changes():
    changes = [(e["name"], e["old"], e["new"]) for e in power_trace(2, 2)
               if e["kind"] == "variable_changed"]
    assert changes == [("R", None, 1), ("R", 1, 2), ("Y", 2, 1), ("R", 2, 4), ("Y", 1, 0)]


def test_trace_loop_conditions():
    checks = [(e["value"], e["iteration"]) for e in power_trace(2, 3)
              if e["kind"] == "condition_evaluated"]
    assert checks == [(True, 0), (True, 1), (True, 2), (False, 3)]


def test_trace_node_info():
    events = power_trace(2, 1)
    assert events[1]["node"]["text"] == "R := 1"
    assert events[1]["node"]["span"]["line"] == 3
    assert events[4]["node"]["text"] == "while Y > 0 do …"
    json.dumps(events, ensure_ascii=False)


def test_trace_with_error():
    result = execute(parse("begin X := 1; Y := Z end"))
    last = result["events"][-1]
    assert last["kind"] == "program_finished"
    assert last["status"] == "error"
    assert last["diagnostic"]["code"] == "runtime.undefined-variable"


def test_if_trace_and_callback():
    received = []
    Interpreter(on_event=received.append).run(
        parse("begin if 1 > 0 then X := 1 else X := 2 end"))
    conds = [e for e in received if e["kind"] == "condition_evaluated"]
    assert len(conds) == 1
    assert conds[0]["iteration"] is None
    assert received[-1]["kind"] == "program_finished"
