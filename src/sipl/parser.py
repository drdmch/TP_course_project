import os

from lark import Lark, Transformer, v_args
from lark.exceptions import UnexpectedCharacters, UnexpectedEOF, UnexpectedToken

from . import ast
from .diagnostics import Diagnostic, SiplSyntaxError

GRAMMAR_FILE = os.path.join(os.path.dirname(__file__), "sipl.lark")

with open(GRAMMAR_FILE, encoding="utf-8") as f:
    GRAMMAR = f.read()

# lexer="basic" keeps keywords (begin, end, ...) from being read as variable names
_parser = Lark(GRAMMAR, parser="lalr", lexer="basic", propagate_positions=True)
_parser_all_tokens = Lark(GRAMMAR, parser="lalr", lexer="basic", propagate_positions=True,
                          keep_all_tokens=True)


def parse(source):
    try:
        tree = _parser.parse(source)
    except (UnexpectedCharacters, UnexpectedToken, UnexpectedEOF) as e:
        raise SiplSyntaxError(make_diagnostic(e, source)) from None
    return ToAst().transform(tree)


def parse_tree(source):
    try:
        return _parser_all_tokens.parse(source)
    except (UnexpectedCharacters, UnexpectedToken, UnexpectedEOF) as e:
        raise SiplSyntaxError(make_diagnostic(e, source)) from None


def make_span(meta):
    return ast.SourceSpan(meta.line, meta.column, meta.end_line, meta.end_column,
                          meta.start_pos, meta.end_pos)


@v_args(meta=True)
class ToAst(Transformer):
    def start(self, meta, ch):
        return ch[0]

    def program(self, meta, ch):
        return ast.Program(ch[0], span=make_span(meta))

    def assign(self, meta, ch):
        return ast.Assign(str(ch[0]), ch[1], span=make_span(meta))

    def seq(self, meta, ch):
        return ast.Seq(ch[0], ch[1], span=make_span(meta))

    def if_stmt(self, meta, ch):
        return ast.If(ch[0], ch[1], ch[2], span=make_span(meta))

    def while_stmt(self, meta, ch):
        return ast.While(ch[0], ch[1], span=make_span(meta))

    def block(self, meta, ch):
        return ast.Block(ch[0], span=make_span(meta))

    def skip(self, meta, ch):
        return ast.Skip(span=make_span(meta))

    def num(self, meta, ch):
        return ast.Num(int(ch[0]), span=make_span(meta))

    def neg_num(self, meta, ch):
        return ast.Num(-int(ch[0]), span=make_span(meta))

    def var(self, meta, ch):
        return ast.Var(str(ch[0]), span=make_span(meta))

    def add(self, meta, ch):
        return ast.BinOp("+", ch[0], ch[1], span=make_span(meta))

    def sub(self, meta, ch):
        return ast.BinOp("-", ch[0], ch[1], span=make_span(meta))

    def mul(self, meta, ch):
        return ast.BinOp("*", ch[0], ch[1], span=make_span(meta))

    def div(self, meta, ch):
        return ast.BinOp("div", ch[0], ch[1], span=make_span(meta))

    def mod(self, meta, ch):
        return ast.BinOp("mod", ch[0], ch[1], span=make_span(meta))

    def eq(self, meta, ch):
        return ast.Compare("=", ch[0], ch[1], span=make_span(meta))

    def gt(self, meta, ch):
        return ast.Compare(">", ch[0], ch[1], span=make_span(meta))

    def or_cond(self, meta, ch):
        return ast.Or(ch[0], ch[1], span=make_span(meta))

    def not_cond(self, meta, ch):
        return ast.Not(ch[0], span=make_span(meta))


TOKEN_NAMES = {
    "BEGIN": "'begin'", "END": "'end'", "IF": "'if'", "THEN": "'then'", "ELSE": "'else'",
    "WHILE": "'while'", "DO": "'do'", "SKIP": "'skip'", "SEMICOLON": "';'",
    "_ASSIGN": "':='", "PLUS": "'+'", "MINUS": "'-'", "STAR": "'*'", "DIV": "'div'",
    "MOD": "'mod'", "LPAR": "'('", "RPAR": "')'", "OR": "'or'", "NOT": "'not'",
    "EQUAL": "'='", "MORETHAN": "'>'", "VAR": "variable", "NUMBER": "number",
    "$END": "end of input",
}


def position_to_span(source, pos):
    line = source.count("\n", 0, pos) + 1
    line_start = source.rfind("\n", 0, pos) + 1
    column = pos - line_start + 1
    return ast.SourceSpan(line, column, line, column + 1, pos, pos + 1)


def make_diagnostic(error, source):
    if isinstance(error, UnexpectedCharacters):
        char = source[error.pos_in_stream]
        return Diagnostic("error", "syntax.unexpected-character",
                          f"Unexpected character '{char}'",
                          position_to_span(source, error.pos_in_stream))

    if isinstance(error, UnexpectedEOF) or error.token.type == "$END":
        end = len(source.rstrip()) - 1
        return Diagnostic("error", "syntax.unexpected-eof",
                          "Unexpected end of input (missing 'end'?)",
                          position_to_span(source, max(end, 0)))

    token = error.token
    expected = []
    for name in sorted(error.expected):
        if name in TOKEN_NAMES:
            expected.append(TOKEN_NAMES[name])
    message = f"Unexpected token '{token}'"
    if expected:
        message += ", expected: " + ", ".join(expected)
    if str(token) == "end" and source[:token.start_pos].rstrip().endswith(";"):
        message += " (extra ';' before 'end'?)"
    span = ast.SourceSpan(token.line, token.column, token.end_line, token.end_column,
                          token.start_pos, token.end_pos)
    return Diagnostic("error", "syntax.unexpected-token", message, span)
