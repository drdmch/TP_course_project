import json
import re

import pytest

from sipl.cli import main
from sipl.visualization import (build_ast_tree, build_parse_tree, compare_html, count_nodes,
                                leaves, to_dot, to_json, to_svg, to_text)
from conftest import example_path, list_examples, read_example

POWER = read_example("valid", "power.sipl")


def labels(tree):
    result = [tree["label"]]
    for child in tree["children"]:
        result += labels(child)
    return result


def find(tree, label, rule=None):
    if tree["label"] == label and (rule is None or tree["rule"] == rule):
        return tree
    for child in tree["children"]:
        found = find(child, label, rule)
        if found is not None:
            return found
    return None


@pytest.mark.parametrize("name", list_examples("valid"))
def test_leaves_give_program_text(name):
    source = read_example("valid", name)
    tree = build_parse_tree(source)
    without_comments = "\n".join(line.split("//")[0] for line in source.split("\n"))
    assert "".join(leaves(tree)) == "".join(without_comments.split())


def test_parse_tree_root():
    tree = build_parse_tree(POWER)
    assert tree["label"] == "P"
    assert tree["rule"] == "P1"
    assert [c["label"] for c in tree["children"]] == ["begin", "S", "end"]


def test_parse_tree_rules():
    tree = build_parse_tree(POWER)
    rules = {node["rule"] for node in all_nodes(tree) if node["rule"]}
    assert rules == {"P1", "S1", "S2", "S4", "S5", "A1", "A2", "A4", "A5", "B2"}


def all_nodes(tree):
    result = [tree]
    for child in tree["children"]:
        result += all_nodes(child)
    return result


def test_parse_tree_all_rules():
    source = ("begin X := (1 + 2) * -3 div 4 mod 5; "
              "if not (X > 0) or X = 1 then skip else begin skip end end")
    rules = {node["rule"] for node in all_nodes(build_parse_tree(source)) if node["rule"]}
    assert rules == {"P1", "S1", "S2", "S3", "S5", "S6", "A1", "A2", "A3", "A5", "A6",
                     "A_div", "A_mod", "B1", "B2", "B3", "B4", "B5"}


def test_parse_tree_nodes_linked_to_source():
    tree = build_parse_tree(POWER)
    loop = find(tree, "S", "S4")
    assert loop["text"].startswith("while Y > 0 do")
    assert loop["span"]["line"] == 4
    cond = find(loop, "b", "B2")
    assert cond["text"] == "Y > 0"
    assert POWER[cond["span"]["start_pos"]:cond["span"]["end_pos"]] == "Y > 0"


def test_variables_and_numbers_have_own_nodes():
    tree = build_parse_tree("begin X := 1 end")
    assign = find(tree, "S", "S1")
    assert assign["children"][0]["label"] == "x"
    assert assign["children"][0]["children"][0]["label"] == "X"
    number = find(tree, "n")
    assert number["children"][0]["label"] == "1"


def test_ast_tree_is_smaller():
    parse_tree = build_parse_tree(POWER)
    ast_tree = build_ast_tree(POWER)
    assert count_nodes(parse_tree) == 52
    assert count_nodes(ast_tree) == 18
    assert "begin" in labels(parse_tree)
    assert "begin" not in labels(ast_tree)
    assert ";" not in labels(ast_tree)


def test_ast_tree_labels():
    tree = build_ast_tree(POWER)
    assert tree["label"] == "Program"
    assert labels(tree)[:4] == ["Program", "Seq", "Assign R", "Num 1"]
    assert find(tree, "Compare >")["text"] == "Y > 0"


def test_text_output():
    text = to_text(build_parse_tree("begin X := 1 end"))
    assert text.split("\n") == [
        'P [P1]   "begin X := 1 end"',
        "  begin",
        '  S [S1]   "X := 1"',
        '    x   "X"',
        "      X",
        "    :=",
        '    a [A1]   "1"',
        '      n   "1"',
        "        1",
        "  end",
    ]


def test_json_output():
    data = json.loads(to_json(build_parse_tree("begin skip end")))
    assert data["label"] == "P"
    assert data["children"][1]["rule"] == "S6"
    assert data["children"][1]["span"]["column"] == 7


def test_dot_output():
    dot = to_dot(build_parse_tree("begin skip end"), prefix="pt")
    assert dot.startswith('digraph "tree" {')
    assert 'pt0 [id="pt0", shape=ellipse, label="P\\nP1"' in dot
    assert 'pt1 [id="pt1", shape=box' in dot
    assert "pt0 -> pt1;" in dot
    assert dot.endswith("}")


def test_dot_escapes_quotes():
    tree = {"label": 'a"b', "rule": None, "text": "", "children": [],
            "span": {"line": 1, "column": 1}}
    assert 'label="a\\"b"' in to_dot(tree)


def test_svg_output():
    tree = build_ast_tree(POWER)
    svg = to_svg(tree, prefix="ast")
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    assert svg.count('class="node"') == count_nodes(tree)
    assert svg.count("<line ") == count_nodes(tree) - 1
    assert 'id="ast0"' in svg and 'id="ast17"' in svg
    assert "<title>2:1  begin R := 1;" in svg


def test_svg_parent_above_middle_of_children():
    svg = to_svg(build_parse_tree("begin skip end"))
    xs = [float(x) for x in re.findall(r'<text x="([0-9.]+)"', svg)]
    ys = [int(y) for y in re.findall(r'<rect x="[0-9.]+" y="([0-9]+)"', svg)]
    # nodes: P (2 text lines), begin, S (2 text lines), skip, end
    p_x, begin_x, s_x, skip_x, end_x = xs[0], xs[2], xs[3], xs[5], xs[6]
    assert abs(p_x - (begin_x + end_x) / 2) < 0.1
    assert s_x == skip_x
    assert ys[0] < ys[1] == ys[2] < ys[3]


def test_svg_escapes_text():
    tree = {"label": "a<b", "rule": None, "text": "a<b", "children": [],
            "span": {"line": 1, "column": 1}}
    assert "a&lt;b" in to_svg(tree)


def test_compare_html():
    page = compare_html(POWER, "power.sipl")
    assert page.startswith("<!doctype html>")
    assert "Parse tree: 52 nodes" in page
    assert "AST: 18 nodes" in page
    assert 'id="pt0"' in page and 'id="ast0"' in page
    assert '"pt0": [' in page


def run_cli(capsys, *args):
    code = main(list(args))
    out, err = capsys.readouterr()
    return code, out, err


def test_cli_tree(capsys):
    code, out, err = run_cli(capsys, "tree", example_path("valid", "power.sipl"))
    assert code == 0
    assert out.startswith("P [P1]")
    assert "leaves: begin R := 1 ; while Y > 0 do" in out


def test_cli_ast_json(capsys):
    code, out, err = run_cli(capsys, "ast", example_path("valid", "power.sipl"), "--format", "json")
    assert json.loads(out)["label"] == "Program"


def test_cli_tree_dot_to_file(tmp_path, capsys):
    path = tmp_path / "tree.dot"
    code, out, err = run_cli(capsys, "tree", example_path("valid", "power.sipl"),
                             "--format", "dot", "-o", str(path))
    assert code == 0
    assert "saved to" in out
    assert path.read_text(encoding="utf-8").startswith("digraph")


def test_cli_compare(tmp_path, capsys):
    path = tmp_path / "compare.html"
    code, out, err = run_cli(capsys, "compare", example_path("valid", "power.sipl"), "-o", str(path))
    assert code == 0
    assert "<svg" in path.read_text(encoding="utf-8")


def test_cli_svg(capsys):
    code, out, err = run_cli(capsys, "ast", example_path("valid", "power.sipl"), "--format", "svg")
    assert code == 0
    assert out.startswith("<svg")


def test_cli_bad_output_path(capsys):
    code, out, err = run_cli(capsys, "tree", example_path("valid", "power.sipl"),
                             "-o", "/no/such/dir/tree.txt")
    assert code == 2


def test_cli_tree_syntax_error(capsys):
    code, out, err = run_cli(capsys, "tree", example_path("invalid", "missing_end.sipl"))
    assert code == 1
