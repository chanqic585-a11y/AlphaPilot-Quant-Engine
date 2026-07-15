"""Recursive runtime for prevalidated factor ASTs; intentionally no eval()."""

from __future__ import annotations

import ast
import operator
from typing import Any, Mapping

from .expression_ast import ParsedExpression
from .operators import OPERATOR_REGISTRY, conditional_select, safe_div


_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Pow: operator.pow,
}
_COMPARE = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def evaluate_expression(expression: ParsedExpression, context: Mapping[str, Any]) -> Any:
    def execute(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return execute(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in context:
                raise KeyError(f"missing factor field: {node.id}")
            return context[node.id]
        if isinstance(node, ast.Call):
            function = OPERATOR_REGISTRY[node.func.id]  # type: ignore[attr-defined]
            return function(*(execute(argument) for argument in node.args))
        if isinstance(node, ast.BinOp):
            left, right = execute(node.left), execute(node.right)
            if isinstance(node.op, ast.Div):
                return safe_div(left, right)
            return _BINARY[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp):
            value = execute(node.operand)
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return value
            return ~value
        if isinstance(node, ast.Compare):
            left = execute(node.left)
            result: Any = True
            for operation, comparator in zip(node.ops, node.comparators, strict=True):
                right = execute(comparator)
                result = result & _COMPARE[type(operation)](left, right)
                left = right
            return result
        if isinstance(node, ast.IfExp):
            return conditional_select(execute(node.test), execute(node.body), execute(node.orelse))
        raise TypeError(f"unhandled validated node: {type(node).__name__}")

    return execute(expression.tree)
