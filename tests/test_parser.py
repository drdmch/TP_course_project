import json

import pytest

from sipl import SiplSyntaxError, parse, parse_tree, to_dict, to_source
from sipl.ast import (Assign, BinOp, Block, Compare, If, Not, Num, Or, Program, Seq, Skip,
                      Var, While, format_tree)
from conftest import list_examples, read_example


def parse_stmt(text):
    return parse("begin " + text + " end").body


def parse_expr(text):
    return parse_stmt("X := " + text).expr


def parse_cond(text):
    return parse_stmt("while " + text + " do skip").cond


def test_power_program():
    program = parse(read_example("valid", "power.sipl"))
    expected = Program(Seq(
        Assign("R", Num(1)),
        While(Compare(">", Var("Y"), Num(0)),
              Block(Seq(Assign("R", BinOp("*", Var("R"), Var("X"))),
                        Assign("Y", BinOp("-", Var("Y"), Num(1))))))))
    assert program == expected


def test_statements():
    assert parse_stmt("skip") == Skip()
    assert parse_stmt("begin skip end") == Block(Skip())
    assert parse_stmt("if X = 1 then skip else Y := 2") == \
        If(Compare("=", Var("X"), Num(1)), Skip(), Assign("Y", Num(2)))


def test_sequence_left_associative():
    assert parse_stmt("A := 1; B := 2; C := 3") == \
        Seq(Seq(Assign("A", Num(1)), Assign("B", Num(2))), Assign("C", Num(3)))


def test_while_stronger_than_sequence():
    stmt = parse_stmt("while X > 0 do X := X - 1; Y := 1")
    assert isinstance(stmt, Seq)
    assert isinstance(stmt.first, While)


def test_arithmetic_priority():
    assert parse_expr("1 + 2 * 3") == BinOp("+", Num(1), BinOp("*", Num(2), Num(3)))
    assert parse_expr("(1 + 2) * 3") == BinOp("*", BinOp("+", Num(1), Num(2)), Num(3))
    assert parse_expr("10 - 3 - 2") == BinOp("-", BinOp("-", Num(10), Num(3)), Num(2))
    assert parse_expr("A div 2 mod 3") == BinOp("mod", BinOp("div", Var("A"), Num(2)), Num(3))


def test_negative_number():
    assert parse_expr("-5") == Num(-5)
    assert parse_expr("X - -1") == BinOp("-", Var("X"), Num(-1))


def test_conditions():
    assert parse_cond("¬ X = 1 ∨ Y > 2") == \
        Or(Not(Compare("=", Var("X"), Num(1))), Compare(">", Var("Y"), Num(2)))
    assert parse_cond("¬ (X = 1 ∨ Y > 2)") == \
        Not(Or(Compare("=", Var("X"), Num(1)), Compare(">", Var("Y"), Num(2))))
    assert parse_cond("(X + 1) > 0") == Compare(">", BinOp("+", Var("X"), Num(1)), Num(0))


def test_or_not_words():
    assert parse_cond("not X > 0 or X = 0") == parse_cond("¬ X > 0 ∨ X = 0")


def test_spans():
    source = read_example("valid", "power.sipl")
    loop = parse(source).body.second
    assert loop.span.line == 4
    assert loop.span.column == 3
    assert source[loop.span.start_pos:loop.span.end_pos].startswith("while Y > 0 do")
    cond = loop.cond
    assert source[cond.span.start_pos:cond.span.end_pos] == "Y > 0"


def test_spans_not_compared():
    assert parse("begin X:=1 end") == parse("begin\n\n   X  :=  1\nend")


def test_to_dict():
    data = to_dict(parse("begin X := 1 end"))
    json.dumps(data)
    assert data["type"] == "Program"
    assert data["body"]["type"] == "Assign"
    assert data["body"]["expr"]["value"] == 1
    assert data["body"]["span"]["line"] == 1


def test_to_dict_without_spans():
    assert to_dict(parse("begin skip end"), with_spans=False) == \
        {"type": "Program", "body": {"type": "Skip"}}


@pytest.mark.parametrize("name", list_examples("valid"))
def test_to_source_gives_same_ast(name):
    program = parse(read_example("valid", name))
    assert parse(to_source(program)) == program


def test_to_source_loop_body():
    stmt = While(Compare(">", Var("X"), Num(0)), Seq(Skip(), Skip()))
    assert to_source(stmt) == "while X > 0 do begin skip; skip end"


def test_format_tree():
    text = format_tree(parse("begin X := 1 end"))
    assert text == "Program\n  Assign X\n    Num 1"


def test_parse_tree_has_all_tokens():
    tree = parse_tree("begin skip end")
    tokens = [str(t) for t in tree.scan_values(lambda v: True)]
    assert tokens == ["begin", "skip", "end"]


def get_error(source):
    with pytest.raises(SiplSyntaxError) as info:
        parse(source)
    return info.value.diagnostic


def test_error_bad_character():
    d = get_error("begin X := 1 @ 2 end")
    assert d.code == "syntax.unexpected-character"
    assert d.span.column == 14


def test_error_unexpected_token():
    d = get_error("begin X = 1 end")
    assert d.code == "syntax.unexpected-token"
    assert "':='" in d.message


def test_error_end_of_file():
    d = get_error("begin X := 1")
    assert d.code == "syntax.unexpected-eof"


def test_error_semicolon_before_end():
    d = get_error("begin X := 1; end")
    assert "extra ';'" in d.message


def test_error_format():
    source = "begin\n  X := 1 @ 2\nend"
    text = get_error(source).format(source, "prog.sipl")
    assert text == ("prog.sipl:2:10: error: Unexpected character '@'\n"
                    "      X := 1 @ 2\n"
                    "             ^")
    assert get_error(source).to_dict()["span"]["line"] == 2
