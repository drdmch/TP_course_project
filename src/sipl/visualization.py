import html
import json

from lark import Token

from . import ast
from .parser import parse, parse_tree

# Lark rule -> (category from the course BNF, rule number)
RULES = {
    "program": ("P", "P1"),
    "assign": ("S", "S1"),
    "seq": ("S", "S2"),
    "if_stmt": ("S", "S3"),
    "while_stmt": ("S", "S4"),
    "block": ("S", "S5"),
    "skip": ("S", "S6"),
    "num": ("a", "A1"),
    "neg_num": ("a", "A1"),
    "var": ("a", "A2"),
    "add": ("a", "A3"),
    "sub": ("a", "A4"),
    "mul": ("a", "A5"),
    "factor": ("a", "A6"),
    "div": ("a", "A_div"),
    "mod": ("a", "A_mod"),
    "eq": ("b", "B1"),
    "gt": ("b", "B2"),
    "or_cond": ("b", "B3"),
    "not_cond": ("b", "B4"),
    "batom": ("b", "B5"),
}


def make_node(label, rule, span, source, children):
    return {
        "label": label,
        "rule": rule,
        "text": source[span.start_pos:span.end_pos],
        "span": span.to_dict(),
        "children": children,
    }


def token_span(tok):
    return ast.SourceSpan(tok.line, tok.column, tok.end_line, tok.end_column,
                          tok.start_pos, tok.end_pos)


def convert_parse_tree(tree, source):
    if isinstance(tree, Token):
        span = token_span(tree)
        leaf = make_node(str(tree), None, span, source, [])
        if tree.type == "VAR":
            return make_node("x", None, span, source, [leaf])
        if tree.type == "NUMBER":
            return make_node("n", None, span, source, [leaf])
        return leaf
    if tree.data == "start":
        return convert_parse_tree(tree.children[0], source)
    label, rule = RULES[tree.data]
    span = ast.SourceSpan(tree.meta.line, tree.meta.column, tree.meta.end_line,
                          tree.meta.end_column, tree.meta.start_pos, tree.meta.end_pos)
    children = [convert_parse_tree(child, source) for child in tree.children]
    return make_node(label, rule, span, source, children)


def build_parse_tree(source):
    return convert_parse_tree(parse_tree(source), source)


def convert_ast(node, source):
    children = [convert_ast(child, source) for child in ast.children(node)]
    return make_node(ast.node_label(node), None, node.span, source, children)


def build_ast_tree(source):
    return convert_ast(parse(source), source)


def count_nodes(tree):
    total = 1
    for child in tree["children"]:
        total += count_nodes(child)
    return total


def leaves(tree):
    if not tree["children"]:
        return [tree["label"]]
    result = []
    for child in tree["children"]:
        result += leaves(child)
    return result


def short(text, limit=40):
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[:limit - 3] + "..."
    return text


def to_text(tree, depth=0):
    line = "  " * depth + tree["label"]
    if tree["rule"]:
        line += f" [{tree['rule']}]"
    if tree["children"]:
        line += f'   "{short(tree["text"])}"'
    lines = [line]
    for child in tree["children"]:
        lines.append(to_text(child, depth + 1))
    return "\n".join(lines)


def to_json(tree):
    return json.dumps(tree, ensure_ascii=False, indent=2)


def dot_escape(text):
    return text.replace("\\", "\\\\").replace('"', '\\"')


def to_dot(tree, prefix="n", title="tree"):
    lines = [f'digraph "{dot_escape(title)}" {{',
             '  node [fontname="Helvetica", fontsize=12];',
             '  edge [arrowhead=none];']
    counter = [0]

    def add(node):
        node_id = f"{prefix}{counter[0]}"
        counter[0] += 1
        span = node["span"]
        tooltip = dot_escape(f"{span['line']}:{span['column']}  {short(node['text'], 60)}")
        if node["children"]:
            label = dot_escape(node["label"])
            if node["rule"]:
                label += "\\n" + dot_escape(node["rule"])
            attrs = f'shape=ellipse, label="{label}"'
        else:
            attrs = f'shape=box, style=filled, fillcolor="#eeeeee", label="{dot_escape(node["label"])}"'
        lines.append(f'  {node_id} [id="{node_id}", {attrs}, tooltip="{tooltip}"];')
        for child in node["children"]:
            child_id = add(child)
            lines.append(f"  {node_id} -> {child_id};")
        return node_id

    add(tree)
    lines.append("}")
    return "\n".join(lines)


CHAR_WIDTH = 7.5
NODE_HEIGHT = 36
LEVEL_HEIGHT = 70
GAP = 12
MARGIN = 10


def node_width(node):
    text = max(node["label"], node["rule"] or "", key=len)
    return max(30, len(text) * CHAR_WIDTH + 16)


def layout(node, depth, items, next_x, prefix):
    # leaves are placed left to right, a parent is placed above the middle of its children
    item = {"id": f"{prefix}{len(items)}", "node": node, "x": 0,
            "y": MARGIN + depth * LEVEL_HEIGHT, "children": []}
    items.append(item)
    if not node["children"]:
        width = node_width(node)
        item["x"] = next_x[0] + width / 2
        next_x[0] += width + GAP
    else:
        for child in node["children"]:
            item["children"].append(layout(child, depth + 1, items, next_x, prefix))
        item["x"] = (item["children"][0]["x"] + item["children"][-1]["x"]) / 2
    return item


def to_svg(tree, prefix="n"):
    items = []
    next_x = [MARGIN]
    layout(tree, 0, items, next_x, prefix)
    width = next_x[0] - GAP + MARGIN
    height = max(item["y"] for item in items) + NODE_HEIGHT + MARGIN

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height}" '
             f'viewBox="0 0 {width:.0f} {height}" font-family="Helvetica, Arial, sans-serif" '
             f'font-size="12">']
    for item in items:
        for child in item["children"]:
            lines.append(f'<line x1="{item["x"]:.1f}" y1="{item["y"] + NODE_HEIGHT}" '
                         f'x2="{child["x"]:.1f}" y2="{child["y"]}" stroke="#555"/>')

    for item in items:
        node = item["node"]
        w = node_width(node)
        x = item["x"] - w / 2
        y = item["y"]
        span = node["span"]
        tooltip = html.escape(f"{span['line']}:{span['column']}  {short(node['text'], 60)}")
        fill = "#ffffff" if node["children"] else "#eeeeee"
        lines.append(f'<g id="{item["id"]}" class="node"><title>{tooltip}</title>')
        lines.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{NODE_HEIGHT}" rx="8" '
                     f'fill="{fill}" stroke="#333"/>')
        if node["rule"]:
            lines.append(f'<text x="{item["x"]:.1f}" y="{y + 15}" text-anchor="middle">'
                         f'{html.escape(node["label"])}</text>')
            lines.append(f'<text x="{item["x"]:.1f}" y="{y + 29}" text-anchor="middle" '
                         f'fill="#777">{html.escape(node["rule"])}</text>')
        else:
            lines.append(f'<text x="{item["x"]:.1f}" y="{y + 22}" text-anchor="middle">'
                         f'{html.escape(node["label"])}</text>')
        lines.append("</g>")
    lines.append("</svg>")
    return "\n".join(lines)


def collect_spans(tree, prefix, result=None):
    if result is None:
        result = {}
    result[f"{prefix}{len(result)}"] = [tree["span"]["start_pos"], tree["span"]["end_pos"]]
    for child in tree["children"]:
        collect_spans(child, prefix, result)
    return result


HTML_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>SIPL: parse tree vs AST</title>
<style>
  body { font-family: sans-serif; margin: 16px; }
  .row { display: flex; gap: 16px; flex-wrap: wrap; align-items: flex-start; }
  .panel { border: 1px solid #ccc; padding: 8px; overflow: auto; max-width: 100%%; }
  pre { font-size: 15px; margin: 0; }
  mark { background: #ffe066; }
  g.node { cursor: pointer; }
  g.node.selected rect { stroke: #d00000; stroke-width: 3; }
</style>
</head>
<body>
<h2>%(title)s</h2>
<p>Parse tree: %(pt_nodes)d nodes, %(pt_leaves)d leaves. AST: %(ast_nodes)d nodes.
Click a node to highlight its source fragment and the nodes with the same fragment in both trees.</p>
<div class="panel"><pre id="code">%(code)s</pre></div>
<div class="row">
  <div class="panel"><h3>Parse tree (concrete syntax)</h3>%(pt_svg)s</div>
  <div class="panel"><h3>AST (abstract syntax)</h3>%(ast_svg)s</div>
</div>
<script>
const spans = %(spans)s;
const source = %(source)s;

function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function select(id) {
  const start = spans[id][0];
  const end = spans[id][1];
  document.getElementById("code").innerHTML = esc(source.slice(0, start)) +
    "<mark>" + esc(source.slice(start, end)) + "</mark>" + esc(source.slice(end));
  for (const key in spans) {
    const g = document.getElementById(key);
    if (g) {
      const same = spans[key][0] === start && spans[key][1] === end;
      g.classList.toggle("selected", same);
    }
  }
}

for (const id in spans) {
  const g = document.getElementById(id);
  if (g) {
    g.addEventListener("click", function () { select(id); });
  }
}
</script>
</body>
</html>
"""


def compare_html(source, title="SIPL program"):
    pt = build_parse_tree(source)
    tree_ast = build_ast_tree(source)
    spans = collect_spans(pt, "pt")
    spans.update(collect_spans(tree_ast, "ast"))
    return HTML_TEMPLATE % {
        "title": html.escape(title),
        "pt_nodes": count_nodes(pt),
        "pt_leaves": len(leaves(pt)),
        "ast_nodes": count_nodes(tree_ast),
        "code": html.escape(source),
        "pt_svg": to_svg(pt, "pt"),
        "ast_svg": to_svg(tree_ast, "ast"),
        "spans": json.dumps(spans),
        "source": json.dumps(source, ensure_ascii=False),
    }
