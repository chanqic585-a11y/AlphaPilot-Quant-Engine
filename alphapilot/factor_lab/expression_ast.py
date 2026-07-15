"""Parsed expression value object."""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedExpression:
    source: str
    tree: ast.Expression
    operator_count: int
    depth: int
