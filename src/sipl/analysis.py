from . import ast


def vars_in(node, result):
    if isinstance(node, ast.Var):
        result.append(node.name)
    for child in ast.children(node):
        vars_in(child, result)
    return result


def find_variables(program):
    # inputs are variables that are read before anything is assigned to them
    inputs = []
    assigned = []

    def read(expr):
        for name in vars_in(expr, []):
            if name not in assigned and name not in inputs:
                inputs.append(name)

    def visit(stmt):
        if isinstance(stmt, ast.Assign):
            read(stmt.expr)
            if stmt.target not in assigned:
                assigned.append(stmt.target)
        elif isinstance(stmt, ast.Seq):
            visit(stmt.first)
            visit(stmt.second)
        elif isinstance(stmt, ast.Block):
            visit(stmt.body)
        elif isinstance(stmt, ast.If):
            read(stmt.cond)
            visit(stmt.then_branch)
            visit(stmt.else_branch)
        elif isinstance(stmt, ast.While):
            read(stmt.cond)
            visit(stmt.body)

    visit(program.body)
    return {"inputs": sorted(inputs), "assigned": sorted(assigned)}
