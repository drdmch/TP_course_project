from dataclasses import dataclass

from . import ast
from .interpreter import DEFAULT_MAX_STEPS


@dataclass
class Const:
    value: int

    def __str__(self):
        return str(self.value)


@dataclass
class Deref:
    name: str

    def __str__(self):
        return self.name + "⇒"


@dataclass
class Sup:
    func: str
    args: list

    def __str__(self):
        args = ", ".join(str(a) for a in self.args)
        return f"S{len(self.args)}({self.func}, {args})"


@dataclass
class AssignT:
    name: str
    f: object

    def __str__(self):
        return f"AS^{self.name}({self.f})"


@dataclass
class SeqT:
    first: object
    second: object

    def __str__(self):
        right = str(self.second)
        if isinstance(self.second, SeqT):
            right = "(" + right + ")"
        return str(self.first) + " · " + right


@dataclass
class IfT:
    cond: object
    then_branch: object
    else_branch: object

    def __str__(self):
        return f"IF({self.cond}, {self.then_branch}, {self.else_branch})"


@dataclass
class WhileT:
    cond: object
    body: object

    def __str__(self):
        return f"WH({self.cond}, {self.body})"


@dataclass
class Id:
    def __str__(self):
        return "id"


ARITH = {
    "+": ("add", "NS_A_Add"),
    "-": ("sub", "NS_A_Sub"),
    "*": ("mult", "NS_A_Mult"),
    "div": ("div", "NS_A_Div"),
    "mod": ("mod", "NS_A_Mod"),
}


class TermBuilder:
    def __init__(self):
        self.steps = []

    def add_step(self, rule, left, right):
        self.steps.append({"rule": rule, "left": left, "right": right})

    def sem_p(self, program):
        body = ast.to_source(program.body)
        self.add_step("NS_Prog", f"sem_P({ast.to_source(program)})", f"sem_S({body})")
        return self.sem_s(program.body)

    def sem_s(self, s):
        left = f"sem_S({ast.to_source(s)})"
        if isinstance(s, ast.Assign):
            self.add_step("NS_Stm_As", left, f"AS^{s.target}(sem_A({ast.to_source(s.expr)}))")
            return AssignT(s.target, self.sem_a(s.expr))
        if isinstance(s, ast.Seq):
            self.add_step("NS_Stm_Seq", left, f"sem_S({ast.to_source(s.first)}) · "
                                              f"sem_S({ast.to_source(s.second)})")
            return SeqT(self.sem_s(s.first), self.sem_s(s.second))
        if isinstance(s, ast.If):
            self.add_step("NS_Stm_If", left, f"IF(sem_B({ast.to_source(s.cond)}), "
                                             f"sem_S({ast.to_source(s.then_branch)}), "
                                             f"sem_S({ast.to_source(s.else_branch)}))")
            return IfT(self.sem_b(s.cond), self.sem_s(s.then_branch), self.sem_s(s.else_branch))
        if isinstance(s, ast.While):
            self.add_step("NS_Stm_Wh", left, f"WH(sem_B({ast.to_source(s.cond)}), "
                                             f"sem_S({ast.to_source(s.body)}))")
            return WhileT(self.sem_b(s.cond), self.sem_s(s.body))
        if isinstance(s, ast.Block):
            self.add_step("NS_Stm_BE", left, f"(sem_S({ast.to_source(s.body)}))")
            return self.sem_s(s.body)
        if isinstance(s, ast.Skip):
            self.add_step("NS_Stm_skip", left, "id")
            return Id()
        raise TypeError(f"Unknown statement: {s}")

    def sem_a(self, a):
        left = f"sem_A({ast.to_source(a)})"
        if isinstance(a, ast.Num):
            self.add_step("NS_A_Num", left, str(a.value))
            return Const(a.value)
        if isinstance(a, ast.Var):
            self.add_step("NS_A_Var", left, a.name + "⇒")
            return Deref(a.name)
        if isinstance(a, ast.BinOp):
            func, rule = ARITH[a.op]
            self.add_step(rule, left, f"S2({func}, sem_A({ast.to_source(a.left)}), "
                                      f"sem_A({ast.to_source(a.right)}))")
            return Sup(func, [self.sem_a(a.left), self.sem_a(a.right)])
        raise TypeError(f"Unknown expression: {a}")

    def sem_b(self, b):
        left = f"sem_B({ast.to_source(b)})"
        if isinstance(b, ast.Compare):
            func, rule = ("eq", "NS_B_eq") if b.op == "=" else ("gr", "NS_B_gr")
            self.add_step(rule, left, f"S2({func}, sem_A({ast.to_source(b.left)}), "
                                      f"sem_A({ast.to_source(b.right)}))")
            return Sup(func, [self.sem_a(b.left), self.sem_a(b.right)])
        if isinstance(b, ast.Or):
            self.add_step("NS_B_or", left, f"S2(or, sem_B({ast.to_source(b.left)}), "
                                           f"sem_B({ast.to_source(b.right)}))")
            return Sup("or", [self.sem_b(b.left), self.sem_b(b.right)])
        if isinstance(b, ast.Not):
            self.add_step("NS_B_neg", left, f"S1(neg, sem_B({ast.to_source(b.operand)}))")
            return Sup("neg", [self.sem_b(b.operand)])
        raise TypeError(f"Unknown condition: {b}")


def build_term(program):
    builder = TermBuilder()
    term = builder.sem_p(program)
    return term, builder.steps


class Undefined(Exception):
    def __init__(self, reason, step_limit=False):
        super().__init__(reason)
        self.reason = reason
        self.step_limit = step_limit


def apply_func(func, args):
    x = args[0]
    if func == "neg":
        return not x
    y = args[1]
    if func == "add":
        return x + y
    if func == "sub":
        return x - y
    if func == "mult":
        return x * y
    if func == "eq":
        return x == y
    if func == "gr":
        return x > y
    if func == "or":
        return x or y
    if y == 0:
        raise Undefined(f"{func}({x}, {y}) is undefined (division by zero)")
    if func == "div":
        return x // y
    if func == "mod":
        return x % y
    raise ValueError(f"Unknown function: {func}")


def show(value):
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def format_state(state):
    parts = [f"{name} ↦ {value}" for name, value in state.items()]
    return "[" + ", ".join(parts) + "]"


class TermEvaluator:
    def __init__(self, max_steps=DEFAULT_MAX_STEPS):
        self.max_steps = max_steps
        self.steps = 0
        self.state_count = 0
        self.trace = []

    def log(self, rule, text, depth):
        self.trace.append({"rule": rule, "text": text, "depth": depth})

    def count_step(self):
        if self.steps >= self.max_steps:
            raise Undefined(f"step limit exceeded ({self.max_steps})", step_limit=True)
        self.steps += 1

    def new_state_name(self):
        self.state_count += 1
        return f"st{self.state_count}"

    def value(self, f, st, name, depth):
        if isinstance(f, Const):
            return f.value
        if isinstance(f, Deref):
            if f.name not in st:
                raise Undefined(f"{f}({name}) is undefined: {f.name} has no value in {name}")
            return st[f.name]
        if isinstance(f, Sup):
            values = [self.value(a, st, name, depth + 1) for a in f.args]
            result = apply_func(f.func, values)
            applied = ", ".join(f"{a}({name})" for a in f.args)
            shown = ", ".join(show(v) for v in values)
            self.log("AF_S", f"{f}({name}) = {f.func}({applied}) = {f.func}({shown}) = "
                             f"{show(result)}", depth)
            return result
        raise TypeError(f"Unknown function term: {f}")

    def apply(self, term, st, name, depth=0):
        if isinstance(term, Id):
            self.count_step()
            self.log("AF_ID", f"id({name}) = {name}", depth)
            return st, name

        if isinstance(term, AssignT):
            self.count_step()
            v = self.value(term.f, st, name, depth + 1)
            new_st = dict(st)
            new_st[term.name] = v
            new_name = self.new_state_name()
            self.log("AF_AS", f"{term}({name}) = {name}∇[{term.name} ↦ {v}] = "
                              f"{format_state(new_st)} = {new_name}", depth)
            return new_st, new_name

        if isinstance(term, SeqT):
            self.log("AF_SEQ", f"({term})({name}) = {term.second}({term.first}({name}))", depth)
            st, name = self.apply(term.first, st, name, depth + 1)
            return self.apply(term.second, st, name, depth + 1)

        if isinstance(term, IfT):
            self.count_step()
            v = self.value(term.cond, st, name, depth + 1)
            branch = term.then_branch if v else term.else_branch
            self.log("AF_IF", f"IF(...)({name}): {term.cond}({name}) = {show(v)}, "
                              f"so the result is {branch}({name})", depth)
            return self.apply(branch, st, name, depth + 1)

        if isinstance(term, WhileT):
            iteration = 0
            while True:
                self.count_step()
                v = self.value(term.cond, st, name, depth + 1)
                if not v:
                    self.log("AF_WH", f"WH(...)({name}): {term.cond}({name}) = false, "
                                      f"loop ends with {name}", depth)
                    return st, name
                iteration += 1
                self.log("AF_WH", f"WH(...)({name}): {term.cond}({name}) = true, "
                                  f"iteration {iteration}", depth)
                st, name = self.apply(term.body, st, name, depth + 1)

        raise TypeError(f"Unknown term: {term}")


def evaluate_term(term, state=None, max_steps=DEFAULT_MAX_STEPS):
    evaluator = TermEvaluator(max_steps)
    st = dict(state or {})
    evaluator.log("start", f"st0 = {format_state(st)}", 0)
    result = {"term": str(term), "input": dict(st)}
    try:
        final, name = evaluator.apply(term, st, "st0")
        result.update({"status": "defined", "state": final, "final_name": name,
                       "reason": None})
    except Undefined as e:
        status = "step_limit" if e.step_limit else "undefined"
        result.update({"status": status, "state": None, "final_name": None,
                       "reason": e.reason})
    result["steps"] = evaluator.steps
    result["trace"] = evaluator.trace
    return result
