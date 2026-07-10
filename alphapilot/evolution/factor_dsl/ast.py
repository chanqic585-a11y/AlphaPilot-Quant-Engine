"""Data-only AST nodes for the restricted AlphaPilot factor DSL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeAlias


@dataclass(frozen=True)
class NumberLiteral:
    value: str


@dataclass(frozen=True)
class FieldReference:
    name: str


@dataclass(frozen=True)
class UnaryOp:
    operator: str
    operand: "Expression"


@dataclass(frozen=True)
class BinaryOp:
    operator: str
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class ComparisonOp:
    operator: str
    left: "Expression"
    right: "Expression"


@dataclass(frozen=True)
class FunctionCall:
    name: str
    args: tuple["Expression", ...]


Expression: TypeAlias = NumberLiteral | FieldReference | UnaryOp | BinaryOp | ComparisonOp | FunctionCall


def ast_to_dict(node: Expression) -> dict[str, Any]:
    if isinstance(node, NumberLiteral):
        return {"type": "number", "value": node.value}
    if isinstance(node, FieldReference):
        return {"type": "field", "name": node.name}
    if isinstance(node, UnaryOp):
        return {"type": "unary", "operator": node.operator, "operand": ast_to_dict(node.operand)}
    if isinstance(node, BinaryOp):
        return {
            "type": "binary",
            "operator": node.operator,
            "left": ast_to_dict(node.left),
            "right": ast_to_dict(node.right),
        }
    if isinstance(node, ComparisonOp):
        return {
            "type": "comparison",
            "operator": node.operator,
            "left": ast_to_dict(node.left),
            "right": ast_to_dict(node.right),
        }
    if isinstance(node, FunctionCall):
        return {"type": "function", "name": node.name, "args": [ast_to_dict(arg) for arg in node.args]}
    raise TypeError(f"Unsupported factor AST node: {type(node).__name__}")
