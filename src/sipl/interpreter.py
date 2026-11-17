from . import ast
from .diagnostics import Diagnostic, SiplRuntimeError

DEFAULT_MAX_STEPS = 100000


def runtime_error(code, message, node):
    return SiplRuntimeError(Diagnostic("error", code, message, node.span))


def eval_aexp(expr, state):
    if isinstance(expr, ast.Num):
        return expr.value
    if isinstance(expr, ast.Var):
        if expr.name not in state:
            raise runtime_error("runtime.undefined-variable",
                                f"Variable '{expr.name}' is undefined", expr)
        return state[expr.name]
    if isinstance(expr, ast.BinOp):
        x = eval_aexp(expr.left, state)
        y = eval_aexp(expr.right, state)
        if expr.op == "+":
            return x + y
        if expr.op == "-":
            return x - y
        if expr.op == "*":
            return x * y
        if y == 0:
            raise runtime_error("runtime.division-by-zero", "Division by zero", expr)
        if expr.op == "div":
            return x // y
        if expr.op == "mod":
            return x % y
    raise TypeError(f"Unknown expression: {expr}")


def eval_bexp(cond, state):
    if isinstance(cond, ast.Compare):
        x = eval_aexp(cond.left, state)
        y = eval_aexp(cond.right, state)
        if cond.op == "=":
            return x == y
        return x > y
    if isinstance(cond, ast.Or):
        # both parts are evaluated, as in S2(or, f1, f2) from the course
        left = eval_bexp(cond.left, state)
        right = eval_bexp(cond.right, state)
        return left or right
    if isinstance(cond, ast.Not):
        return not eval_bexp(cond.operand, state)
    raise TypeError(f"Unknown condition: {cond}")


def short_text(node):
    if isinstance(node, ast.While):
        return "while " + ast.to_source(node.cond) + " do …"
    if isinstance(node, ast.If):
        return "if " + ast.to_source(node.cond) + " then … else …"
    return ast.to_source(node)


def node_info(node):
    span = None
    if node.span is not None:
        span = node.span.to_dict()
    return {"type": type(node).__name__, "text": short_text(node), "span": span}


class Interpreter:
    def __init__(self, max_steps=DEFAULT_MAX_STEPS, on_event=None):
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        self.max_steps = max_steps
        self.on_event = on_event
        self.state = {}
        self.steps = 0
        self.events = []

    def emit(self, kind, **data):
        event = {"seq": len(self.events) + 1, "kind": kind}
        event.update(data)
        self.events.append(event)
        if self.on_event is not None:
            self.on_event(event)

    def count_step(self, node):
        if self.steps >= self.max_steps:
            raise runtime_error("runtime.step-limit",
                                f"Step limit exceeded ({self.max_steps})", node)
        self.steps += 1

    def run(self, program, state=None):
        self.state = dict(state or {})
        self.steps = 0
        self.events = []
        self.emit("program_started", state=dict(self.state))
        try:
            self.exec_stmt(program.body)
        except SiplRuntimeError as e:
            status = "error"
            if e.diagnostic.code == "runtime.step-limit":
                status = "step_limit"
            self.emit("program_finished", status=status, steps=self.steps,
                      state=dict(self.state), diagnostic=e.diagnostic.to_dict())
            raise
        self.emit("program_finished", status="ok", steps=self.steps,
                  state=dict(self.state), diagnostic=None)
        return self.state

    def exec_stmt(self, stmt):
        if isinstance(stmt, ast.Seq):
            self.exec_stmt(stmt.first)
            self.exec_stmt(stmt.second)
            return
        if isinstance(stmt, ast.Block):
            self.exec_stmt(stmt.body)
            return

        self.emit("before_statement", node=node_info(stmt), state=dict(self.state))

        if isinstance(stmt, ast.Assign):
            self.count_step(stmt)
            value = eval_aexp(stmt.expr, self.state)
            old = self.state.get(stmt.target)
            self.state[stmt.target] = value
            self.emit("variable_changed", node=node_info(stmt), name=stmt.target,
                      old=old, new=value)

        elif isinstance(stmt, ast.Skip):
            self.count_step(stmt)

        elif isinstance(stmt, ast.If):
            self.count_step(stmt)
            value = eval_bexp(stmt.cond, self.state)
            self.emit("condition_evaluated", node=node_info(stmt.cond),
                      owner=node_info(stmt), value=value, iteration=None)
            if value:
                self.exec_stmt(stmt.then_branch)
            else:
                self.exec_stmt(stmt.else_branch)

        elif isinstance(stmt, ast.While):
            iteration = 0
            while True:
                self.count_step(stmt)
                value = eval_bexp(stmt.cond, self.state)
                self.emit("condition_evaluated", node=node_info(stmt.cond),
                          owner=node_info(stmt), value=value, iteration=iteration)
                if not value:
                    break
                self.exec_stmt(stmt.body)
                iteration += 1

        else:
            raise TypeError(f"Unknown statement: {stmt}")

        self.emit("after_statement", node=node_info(stmt), state=dict(self.state))


def run(program, state=None, max_steps=DEFAULT_MAX_STEPS):
    return Interpreter(max_steps).run(program, state)


def execute(program, state=None, max_steps=DEFAULT_MAX_STEPS):
    interp = Interpreter(max_steps)
    try:
        interp.run(program, state)
    except SiplRuntimeError:
        pass
    last = interp.events[-1]
    return {
        "status": last["status"],
        "steps": last["steps"],
        "state": last["state"],
        "diagnostic": last["diagnostic"],
        "events": interp.events,
    }
