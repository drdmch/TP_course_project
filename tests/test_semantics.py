import json
import os

import pytest

from sipl import parse
from sipl.cli import main
from sipl.interpreter import execute
from sipl.semantics import (AssignT, Const, Deref, Id, IfT, SeqT, Sup, WhileT, build_term,
                            evaluate_term)
from conftest import TESTS_DIR, example_path, list_examples, read_example

GOLDEN_DIR = os.path.join(TESTS_DIR, "golden")
POWER_TERM = "AS^R(1) · WH(S2(gr, Y⇒, 0), AS^R(S2(mult, R⇒, X⇒)) · AS^Y(S2(sub, Y⇒, 1)))"


def term_of(text):
    term, steps = build_term(parse(text))
    return term


def stmt_term(body):
    return term_of("begin " + body + " end")


@pytest.mark.parametrize("name", list_examples("valid"))
def test_golden_terms(name):
    golden_file = os.path.join(GOLDEN_DIR, name.replace(".sipl", ".term"))
    with open(golden_file, encoding="utf-8") as f:
        expected = f.read().strip()
    assert str(term_of(read_example("valid", name))) == expected


def test_power_term_from_practicum():
    assert str(term_of(read_example("valid", "power.sipl"))) == POWER_TERM


def test_power_rules_order():
    _, steps = build_term(parse(read_example("valid", "power.sipl")))
    rules = [s["rule"] for s in steps]
    assert rules == ["NS_Prog", "NS_Stm_Seq", "NS_Stm_As", "NS_A_Num",
                     "NS_Stm_Wh", "NS_B_gr", "NS_A_Var", "NS_A_Num",
                     "NS_Stm_BE", "NS_Stm_Seq",
                     "NS_Stm_As", "NS_A_Mult", "NS_A_Var", "NS_A_Var",
                     "NS_Stm_As", "NS_A_Sub", "NS_A_Var", "NS_A_Num"]
    assert steps[2] == {"rule": "NS_Stm_As", "left": "sem_S(R := 1)",
                        "right": "AS^R(sem_A(1))"}
    assert steps[5] == {"rule": "NS_B_gr", "left": "sem_B(Y > 0)",
                        "right": "S2(gr, sem_A(Y), sem_A(0))"}


def test_all_statements():
    assert stmt_term("skip") == Id()
    assert stmt_term("X := 1") == AssignT("X", Const(1))
    assert stmt_term("X := Y") == AssignT("X", Deref("Y"))
    assert stmt_term("skip; skip") == SeqT(Id(), Id())
    assert stmt_term("begin skip end") == Id()
    assert stmt_term("if X = 1 then skip else skip") == \
        IfT(Sup("eq", [Deref("X"), Const(1)]), Id(), Id())
    assert stmt_term("while X > 0 do skip") == \
        WhileT(Sup("gr", [Deref("X"), Const(0)]), Id())


def test_all_functions():
    assert str(stmt_term("X := 1 + 2 - 3 * 4 div 5 mod 6")) == \
        "AS^X(S2(sub, S2(add, 1, 2), S2(mod, S2(div, S2(mult, 3, 4), 5), 6)))"
    assert str(stmt_term("if ¬ X > 0 ∨ X = 0 then skip else skip")) == \
        "IF(S2(or, S1(neg, S2(gr, X⇒, 0)), S2(eq, X⇒, 0)), id, id)"


def test_sequence_inside_sequence_gets_brackets():
    assert str(SeqT(Id(), SeqT(Id(), Id()))) == "id · (id · id)"


def test_eval_power_like_practicum():
    term = term_of(read_example("valid", "power.sipl"))
    result = evaluate_term(term, {"X": 5, "Y": 2})
    assert result["status"] == "defined"
    assert result["state"] == {"X": 5, "Y": 0, "R": 25}
    texts = [t["text"] for t in result["trace"]]
    assert "AS^R(1)(st0) = st0∇[R ↦ 1] = [X ↦ 5, Y ↦ 2, R ↦ 1] = st1" in texts
    assert "S2(gr, Y⇒, 0)(st1) = gr(Y⇒(st1), 0(st1)) = gr(2, 0) = true" in texts
    assert "S2(mult, R⇒, X⇒)(st3) = mult(R⇒(st3), X⇒(st3)) = mult(5, 5) = 25" in texts
    assert "S2(gr, Y⇒, 0)(st5) = gr(Y⇒(st5), 0(st5)) = gr(0, 0) = false" in texts


def test_eval_rules_used():
    term = term_of(read_example("valid", "power.sipl"))
    rules = {t["rule"] for t in evaluate_term(term, {"X": 2, "Y": 1})["trace"]}
    assert rules == {"start", "AF_SEQ", "AF_AS", "AF_S", "AF_WH"}
    if_rules = {t["rule"] for t in evaluate_term(stmt_term("if 1 = 1 then skip else skip"))["trace"]}
    assert {"AF_IF", "AF_ID"} <= if_rules


def test_eval_if_branches():
    term = stmt_term("if X > 0 then R := 1 else R := 2")
    assert evaluate_term(term, {"X": 5})["state"]["R"] == 1
    assert evaluate_term(term, {"X": 0})["state"]["R"] == 2


def test_eval_undefined_variable():
    result = evaluate_term(term_of(read_example("valid", "power.sipl")), {"Y": 2})
    assert result["status"] == "undefined"
    assert result["state"] is None
    assert "X⇒(st1) is undefined" in result["reason"]


def test_eval_division_by_zero():
    result = evaluate_term(stmt_term("X := 1 div 0"))
    assert result["status"] == "undefined"
    assert "division by zero" in result["reason"]


def test_eval_endless_loop():
    result = evaluate_term(stmt_term("while 1 = 1 do skip"), max_steps=100)
    assert result["status"] == "step_limit"
    assert result["steps"] == 100


@pytest.mark.parametrize("name, state", [
    ("power", {"X": 3, "Y": 4}),
    ("factorial", {"N": 5}),
    ("gcd", {"X": 12, "Y": 18}),
    ("log2", {"N": 17}),
    ("double_factorial", {"N": 2}),
    ("progression_sum", {"N": 3}),
    ("max", {"X": 9, "Y": 9}),
    ("abs", {"X": -4}),
    ("mod_parity", {"N": 5}),
    ("ascii_logic", {"X": 7}),
    ("nested_blocks", {}),
    ("skip_only", {"Z": 1}),
])
def test_term_gives_same_result_as_interpreter(name, state):
    program = parse(read_example("valid", name + ".sipl"))
    term, _ = build_term(program)
    assert evaluate_term(term, state)["state"] == execute(program, state)["state"]


def run_cli(capsys, *args):
    code = main(list(args))
    out, err = capsys.readouterr()
    return code, out


def test_cli_term(capsys):
    code, out = run_cli(capsys, "term", example_path("valid", "power.sipl"))
    assert code == 0
    assert out.strip() == POWER_TERM


def test_cli_term_steps(capsys):
    code, out = run_cli(capsys, "term", example_path("valid", "power.sipl"), "--steps")
    assert "NS_Stm_As: sem_S(R := 1) = AS^R(sem_A(1))" in out


def test_cli_term_json(capsys):
    code, out = run_cli(capsys, "term", example_path("valid", "power.sipl"), "--json")
    data = json.loads(out)
    assert data["term"] == POWER_TERM
    assert data["steps"][0]["rule"] == "NS_Prog"


def test_cli_eval(capsys):
    code, out = run_cli(capsys, "eval", example_path("valid", "power.sipl"), "-s", "X=5", "-s", "Y=2")
    assert code == 0
    assert "result: st5 = [X ↦ 5, Y ↦ 0, R ↦ 25]" in out


def test_cli_eval_undefined(capsys):
    code, out = run_cli(capsys, "eval", example_path("valid", "power.sipl"), "-s", "Y=2")
    assert code == 3
    assert "result: undefined" in out


def test_cli_eval_json(capsys):
    code, out = run_cli(capsys, "eval", example_path("valid", "power.sipl"),
                        "-s", "X=2", "-s", "Y=1", "--json")
    data = json.loads(out)
    assert data["status"] == "defined"
    assert data["state"]["R"] == 2
    assert data["trace"][0]["rule"] == "start"


def test_cli_eval_step_limit(tmp_path, capsys):
    path = tmp_path / "loop.sipl"
    path.write_text("begin while 1 = 1 do skip end", encoding="utf-8")
    code, out = run_cli(capsys, "eval", str(path), "--max-steps", "10")
    assert code == 4
