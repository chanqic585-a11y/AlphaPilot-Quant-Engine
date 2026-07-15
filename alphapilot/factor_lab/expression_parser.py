"""Parse a narrow factor expression language without dynamic execution."""

from __future__ import annotations

import ast

from .expression_ast import ParsedExpression
from .operators import OPERATOR_REGISTRY


_ALLOWED_BINARY = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_ALLOWED_UNARY = (ast.UAdd, ast.USub, ast.Not)
_ALLOWED_COMPARE = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
_REJECTED_REPEAT = frozenset({"rank", "ts_mean", "ts_corr"})


def parse_expression(source: str, *, max_depth: int = 4, max_operators: int = 8) -> ParsedExpression:
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        raise ValueError("invalid factor expression syntax") from exc
    operator_count = 0
    deepest_call = 0

    def visit(node: ast.AST, call_depth: int = 0, parents: tuple[str, ...] = ()) -> None:
        nonlocal operator_count, deepest_call
        if isinstance(node, ast.Expression):
            visit(node.body, call_depth, parents)
            return
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float, bool)):
                raise ValueError("only numeric and boolean literals are allowed")
            return
        if isinstance(node, ast.Name):
            if node.id.startswith("_"):
                raise ValueError("private names are not allowed")
            return
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in OPERATOR_REGISTRY:
                raise ValueError("function is not in the operator whitelist")
            if node.keywords:
                raise ValueError("operator arguments must be positional")
            name = node.func.id
            if name in _REJECTED_REPEAT and name in parents:
                raise ValueError(f"unexplained nested {name} is not allowed")
            operator_count += 1
            deepest_call = max(deepest_call, call_depth + 1)
            for argument in node.args:
                visit(argument, call_depth + 1, (*parents, name))
            return
        if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINARY):
            visit(node.left, call_depth, parents)
            visit(node.right, call_depth, parents)
            return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARY):
            visit(node.operand, call_depth, parents)
            return
        if isinstance(node, ast.Compare) and all(isinstance(item, _ALLOWED_COMPARE) for item in node.ops):
            visit(node.left, call_depth, parents)
            for comparator in node.comparators:
                visit(comparator, call_depth, parents)
            return
        if isinstance(node, ast.IfExp):
            visit(node.test, call_depth, parents)
            visit(node.body, call_depth, parents)
            visit(node.orelse, call_depth, parents)
            return
        raise ValueError(f"expression node is not allowed: {type(node).__name__}")

    visit(tree)
    if deepest_call > max_depth:
        raise ValueError(f"expression depth exceeds {max_depth}")
    if operator_count > max_operators:
        raise ValueError(f"operator count exceeds {max_operators}")
    return ParsedExpression(source=source, tree=tree, operator_count=operator_count, depth=deepest_call)
