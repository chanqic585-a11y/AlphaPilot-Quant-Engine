"""Type, complexity, window, and domain validation for factor expressions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .ast import ComparisonOp, Expression, FieldReference, FunctionCall, NumberLiteral
from .canonicalizer import canonicalize
from .operators import OPERATOR_SPECS, OperatorSpec


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: str


@dataclass(frozen=True)
class FactorValidationResult:
    valid: bool
    issues: list[ValidationIssue]
    requiredFields: list[str]
    domainRequirements: list[str]
    nodeCount: int
    maxDepth: int


def _number_value(node: Expression) -> Decimal | None:
    if not isinstance(node, NumberLiteral):
        return None
    try:
        return Decimal(node.value)
    except InvalidOperation:
        return None


def validate_factor_expression(
    node: Expression,
    *,
    field_types: dict[str, str],
    max_window: int = 512,
    max_depth: int = 12,
    max_nodes: int = 128,
) -> FactorValidationResult:
    root = canonicalize(node)
    normalized_field_types = {name.lower(): value for name, value in field_types.items()}
    issues: list[ValidationIssue] = []
    required_fields: set[str] = set()
    domain_requirements: set[str] = set()
    node_count = 0
    observed_depth = 0

    def issue(code: str, message: str, path: str) -> None:
        issues.append(ValidationIssue(code, message, path))

    def validate_window(spec: OperatorSpec, args: tuple[Expression, ...], path: str) -> None:
        for index in spec.windowArgs:
            if index >= len(args):
                continue
            value = _number_value(args[index])
            if value is None or value != value.to_integral_value():
                issue("window_must_be_integer", f"{spec.name} window must be an integer", path)
                continue
            if index in spec.offsetArgs and value < 0:
                issue("future_offset_forbidden", f"{spec.name} cannot use a negative offset", path)
            elif value <= 0 or value > max_window:
                issue(
                    "window_out_of_range",
                    f"{spec.name} window must be between 1 and {max_window}",
                    path,
                )

    def visit(current: Expression, depth: int, path: str) -> str:
        nonlocal node_count, observed_depth
        node_count += 1
        observed_depth = max(observed_depth, depth)
        if isinstance(current, NumberLiteral):
            return "number"
        if isinstance(current, FieldReference):
            required_fields.add(current.name)
            field_type = normalized_field_types.get(current.name)
            if field_type is None:
                issue("unknown_field", f"Unknown factor field: {current.name}", path)
                return "unknown"
            return field_type
        if isinstance(current, ComparisonOp):
            left_type = visit(current.left, depth + 1, f"{path}.left")
            right_type = visit(current.right, depth + 1, f"{path}.right")
            if left_type not in {"number", "unknown"} or right_type not in {"number", "unknown"}:
                issue("type_mismatch", "Comparisons require numeric operands", path)
            return "bool"
        if isinstance(current, FunctionCall):
            spec = OPERATOR_SPECS.get(current.name)
            if spec is None:
                issue("unknown_operator", f"Unknown factor operator: {current.name}", path)
                for index, arg in enumerate(current.args):
                    visit(arg, depth + 1, f"{path}.args[{index}]")
                return "unknown"
            if not spec.minArgs <= len(current.args) <= spec.maxArgs:
                issue(
                    "invalid_arity",
                    f"{current.name} expects {spec.minArgs}..{spec.maxArgs} arguments",
                    path,
                )
            argument_types = [
                visit(arg, depth + 1, f"{path}.args[{index}]")
                for index, arg in enumerate(current.args)
            ]
            validate_window(spec, current.args, path)
            domain_requirements.update(spec.domainRequirements)
            if current.name == "safe_divide" and len(current.args) >= 2:
                denominator = _number_value(current.args[1])
                if denominator == 0:
                    issue("division_by_zero_literal", "Division by literal zero is forbidden", path)
            for index, expected in enumerate(spec.argumentTypes):
                if index >= len(argument_types):
                    break
                actual = argument_types[index]
                if actual not in {expected, "unknown"}:
                    issue(
                        "type_mismatch",
                        f"{current.name} argument {index + 1} requires {expected}, got {actual}",
                        path,
                    )
            if not spec.argumentTypes:
                for actual in argument_types:
                    if actual not in {"number", "unknown"}:
                        issue("type_mismatch", f"{current.name} requires numeric arguments", path)
                        break
            return spec.resultType
        issue("unsupported_ast_node", f"Unsupported AST node: {type(current).__name__}", path)
        return "unknown"

    visit(root, 1, "root")
    if observed_depth > max_depth:
        issue("max_depth_exceeded", f"Expression depth {observed_depth} exceeds {max_depth}", "root")
    if node_count > max_nodes:
        issue("max_nodes_exceeded", f"Expression node count {node_count} exceeds {max_nodes}", "root")
    return FactorValidationResult(
        valid=not issues,
        issues=issues,
        requiredFields=sorted(required_fields),
        domainRequirements=sorted(domain_requirements),
        nodeCount=node_count,
        maxDepth=observed_depth,
    )
