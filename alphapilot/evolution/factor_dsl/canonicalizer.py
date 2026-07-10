"""Canonicalize equivalent factor expressions into stable identities."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from alphapilot.evolution.registry.hashing import stable_hash

from .ast import (
    BinaryOp,
    ComparisonOp,
    Expression,
    FieldReference,
    FunctionCall,
    NumberLiteral,
    UnaryOp,
    ast_to_dict,
)
from .operators import COMMUTATIVE_FUNCTIONS, LEGACY_FUNCTION_ALIASES


BINARY_FUNCTIONS = {
    "+": "safe_add",
    "-": "safe_subtract",
    "*": "safe_multiply",
    "/": "safe_divide",
}


def _canonical_number(value: str) -> str:
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric literal: {value}") from exc
    if not number.is_finite():
        raise ValueError("Non-finite numeric literal is forbidden")
    if number == 0:
        return "0"
    if number == number.to_integral_value():
        return str(int(number))
    return format(number.normalize(), "f")


def canonical_field_name(name: str) -> str:
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    snake = re.sub(r"[^A-Za-z0-9_]+", "_", snake)
    return re.sub(r"_+", "_", snake).strip("_").lower()


def canonicalize(node: Expression) -> Expression:
    if isinstance(node, NumberLiteral):
        return NumberLiteral(_canonical_number(node.value))
    if isinstance(node, FieldReference):
        return FieldReference(canonical_field_name(node.name))
    if isinstance(node, UnaryOp):
        operand = canonicalize(node.operand)
        if node.operator == "+":
            return operand
        if node.operator == "-" and isinstance(operand, NumberLiteral):
            return NumberLiteral(_canonical_number(f"-{operand.value}"))
        if node.operator == "-":
            return canonicalize(FunctionCall("safe_multiply", (NumberLiteral("-1"), operand)))
        raise ValueError(f"Unsupported unary operator: {node.operator}")
    if isinstance(node, BinaryOp):
        function_name = BINARY_FUNCTIONS.get(node.operator)
        if not function_name:
            raise ValueError(f"Unsupported binary operator: {node.operator}")
        return canonicalize(FunctionCall(function_name, (node.left, node.right)))
    if isinstance(node, ComparisonOp):
        return ComparisonOp(node.operator, canonicalize(node.left), canonicalize(node.right))
    if isinstance(node, FunctionCall):
        name = LEGACY_FUNCTION_ALIASES.get(node.name, node.name)
        args = tuple(canonicalize(arg) for arg in node.args)
        if node.name == "ts_return":
            if len(args) != 2:
                return FunctionCall(node.name, args)
            value, window = args
            return canonicalize(
                FunctionCall(
                    "safe_divide",
                    (
                        FunctionCall("delta", (value, window)),
                        FunctionCall("lag", (value, window)),
                    ),
                )
            )
        if name in COMMUTATIVE_FUNCTIONS:
            args = tuple(sorted(args, key=canonical_expression))
        return FunctionCall(name, args)
    raise TypeError(f"Unsupported factor AST node: {type(node).__name__}")


def canonical_expression(node: Expression) -> str:
    if isinstance(node, NumberLiteral):
        return node.value
    if isinstance(node, FieldReference):
        return node.name
    if isinstance(node, UnaryOp):
        return f"{node.operator}{canonical_expression(node.operand)}"
    if isinstance(node, BinaryOp):
        return f"({canonical_expression(node.left)}{node.operator}{canonical_expression(node.right)})"
    if isinstance(node, ComparisonOp):
        return f"({canonical_expression(node.left)}{node.operator}{canonical_expression(node.right)})"
    if isinstance(node, FunctionCall):
        return f"{node.name}({','.join(canonical_expression(arg) for arg in node.args)})"
    raise TypeError(f"Unsupported factor AST node: {type(node).__name__}")


def expression_id(node: Expression) -> str:
    canonical = canonicalize(node)
    return stable_hash(ast_to_dict(canonical), prefix="factor_expression")
