from dataclasses import dataclass, field


@dataclass
class SourceSpan:
    line: int
    column: int
    end_line: int
    end_column: int
    start_pos: int
    end_pos: int

    def to_dict(self):
        return dict(self.__dict__)

    def __str__(self):
        return f"{self.line}:{self.column}-{self.end_line}:{self.end_column}"


@dataclass
class Num:
    value: int
    span: SourceSpan = field(default=None, compare=False, repr=False)


@dataclass
class Var:
    name: str
    span: SourceSpan = field(default=None, compare=False, repr=False)


@dataclass
class BinOp:
    op: str
    left: object
    right: object
    span: SourceSpan = field(default=None, compare=False, repr=False)


@dataclass
class Compare:
    op: str
    left: object
    right: object
    span: SourceSpan = field(default=None, compare=False, repr=False)


@dataclass
class Or:
    left: object
    right: object
    span: SourceSpan = field(default=None, compare=False, repr=False)


@dataclass
class Not:
    operand: object
    span: SourceSpan = field(default=None, compare=False, repr=False)


@dataclass
class Assign:
    target: str
    expr: object
    span: SourceSpan = field(default=None, compare=False, repr=False)


@dataclass
class Seq:
    first: object
    second: object
    span: SourceSpan = field(default=None, compare=False, repr=False)


@dataclass
class If:
    cond: object
    then_branch: object
    else_branch: object
    span: SourceSpan = field(default=None, compare=False, repr=False)


@dataclass
class While:
    cond: object
    body: object
    span: SourceSpan = field(default=None, compare=False, repr=False)


@dataclass
class Block:
    body: object
    span: SourceSpan = field(default=None, compare=False, repr=False)


@dataclass
class Skip:
    span: SourceSpan = field(default=None, compare=False, repr=False)


@dataclass
class Program:
    body: object
    span: SourceSpan = field(default=None, compare=False, repr=False)


def is_node(value):
    return not isinstance(value, (int, str)) and value is not None


def children(node):
    result = []
    for name, value in node.__dict__.items():
        if name != "span" and is_node(value):
            result.append(value)
    return result


def to_dict(node, with_spans=True):
    result = {"type": type(node).__name__}
    for name, value in node.__dict__.items():
        if name == "span":
            continue
        if is_node(value):
            result[name] = to_dict(value, with_spans)
        else:
            result[name] = value
    if with_spans and node.span is not None:
        result["span"] = node.span.to_dict()
    return result


def to_source(node):
    if isinstance(node, Program):
        return "begin " + to_source(node.body) + " end"
    if isinstance(node, Assign):
        return node.target + " := " + to_source(node.expr)
    if isinstance(node, Seq):
        return to_source(node.first) + "; " + to_source(node.second)
    if isinstance(node, If):
        return ("if " + to_source(node.cond) + " then " + _inner(node.then_branch)
                + " else " + _inner(node.else_branch))
    if isinstance(node, While):
        return "while " + to_source(node.cond) + " do " + _inner(node.body)
    if isinstance(node, Block):
        return "begin " + to_source(node.body) + " end"
    if isinstance(node, Skip):
        return "skip"
    if isinstance(node, Num):
        return str(node.value)
    if isinstance(node, Var):
        return node.name
    if isinstance(node, BinOp):
        return _operand(node.left) + " " + node.op + " " + _operand(node.right)
    if isinstance(node, Compare):
        return to_source(node.left) + " " + node.op + " " + to_source(node.right)
    if isinstance(node, Or):
        right = to_source(node.right)
        if isinstance(node.right, Or):
            right = "(" + right + ")"
        return to_source(node.left) + " ∨ " + right
    if isinstance(node, Not):
        return "¬(" + to_source(node.operand) + ")"
    raise TypeError(f"Unknown node: {node}")


def _operand(expr):
    if isinstance(expr, BinOp):
        return "(" + to_source(expr) + ")"
    return to_source(expr)


def _inner(stmt):
    # a sequence inside while/if must be wrapped in begin ... end
    if isinstance(stmt, Seq):
        return "begin " + to_source(stmt) + " end"
    return to_source(stmt)


def node_label(node):
    if isinstance(node, Num):
        return "Num " + str(node.value)
    if isinstance(node, Var):
        return "Var " + node.name
    if isinstance(node, Assign):
        return "Assign " + node.target
    if isinstance(node, (BinOp, Compare)):
        return type(node).__name__ + " " + node.op
    return type(node).__name__


def format_tree(node, with_spans=False, depth=0):
    line = "  " * depth + node_label(node)
    if with_spans and node.span is not None:
        line += "  [" + str(node.span) + "]"
    lines = [line]
    for child in children(node):
        lines.append(format_tree(child, with_spans, depth + 1))
    return "\n".join(lines)
