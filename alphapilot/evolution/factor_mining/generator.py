"""Generate bounded candidates only by mutating already parsed factor ASTs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from alphapilot.evolution.factor_dsl.ast import (
    ComparisonOp,
    Expression,
    FieldReference,
    FunctionCall,
    NumberLiteral,
)
from alphapilot.evolution.factor_dsl.canonicalizer import (
    canonical_expression,
    canonical_field_name,
    canonicalize,
    expression_id,
)
from alphapilot.evolution.factor_dsl.operators import OPERATOR_SPECS
from alphapilot.evolution.factor_dsl.validator import validate_factor_expression
from alphapilot.evolution.registry.hashing import stable_hash


@dataclass(frozen=True)
class FactorSeed:
    factorId: str
    expressionAst: Expression


@dataclass(frozen=True)
class GenerationConfig:
    allowedWindows: tuple[int, ...] = (3, 6, 12, 24, 48, 72)
    fieldReplacements: dict[str, tuple[str, ...]] = field(default_factory=dict)
    crossOperators: tuple[str, ...] = ("safe_add", "safe_multiply")
    maxCandidates: int = 64


@dataclass(frozen=True)
class GeneratedFactorCandidate:
    candidateId: str
    expressionId: str
    parentIds: tuple[str, ...]
    mutationType: str
    mutationDetail: dict[str, Any]
    expressionAst: Expression
    canonicalExpression: str
    researchOnly: bool = True

    @classmethod
    def from_expression(
        cls,
        *,
        parentIds: tuple[str, ...],
        mutationType: str,
        expression: Expression,
        mutationDetail: dict[str, Any] | None = None,
    ) -> "GeneratedFactorCandidate":
        canonical = canonicalize(expression)
        factor_expression_id = expression_id(canonical)
        detail = mutationDetail or {}
        candidate_id = stable_hash(
            {
                "expressionId": factor_expression_id,
                "parents": sorted(parentIds),
                "mutationType": mutationType,
                "mutationDetail": detail,
            },
            prefix="factor_candidate",
        )
        return cls(
            candidateId=candidate_id,
            expressionId=factor_expression_id,
            parentIds=tuple(sorted(parentIds)),
            mutationType=mutationType,
            mutationDetail=detail,
            expressionAst=canonical,
            canonicalExpression=canonical_expression(canonical),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidateId": self.candidateId,
            "expressionId": self.expressionId,
            "parentIds": list(self.parentIds),
            "mutationType": self.mutationType,
            "mutationDetail": self.mutationDetail,
            "canonicalExpression": self.canonicalExpression,
            "researchOnly": self.researchOnly,
        }


def _replace_windows(node: Expression, replacement: int) -> Expression:
    if isinstance(node, FunctionCall):
        spec = OPERATOR_SPECS.get(node.name)
        args = list(node.args)
        if spec:
            for index in spec.windowArgs:
                if index < len(args):
                    args[index] = NumberLiteral(str(replacement))
        return FunctionCall(node.name, tuple(_replace_windows(arg, replacement) for arg in args))
    if isinstance(node, ComparisonOp):
        return ComparisonOp(
            node.operator,
            _replace_windows(node.left, replacement),
            _replace_windows(node.right, replacement),
        )
    return node


def _replace_field(node: Expression, source: str, target: str) -> Expression:
    if isinstance(node, FieldReference):
        return FieldReference(target) if node.name == source else node
    if isinstance(node, FunctionCall):
        return FunctionCall(node.name, tuple(_replace_field(arg, source, target) for arg in node.args))
    if isinstance(node, ComparisonOp):
        return ComparisonOp(
            node.operator,
            _replace_field(node.left, source, target),
            _replace_field(node.right, source, target),
        )
    return node


def _fields_in(node: Expression) -> set[str]:
    if isinstance(node, FieldReference):
        return {node.name}
    if isinstance(node, FunctionCall):
        return set().union(*(_fields_in(arg) for arg in node.args)) if node.args else set()
    if isinstance(node, ComparisonOp):
        return _fields_in(node.left) | _fields_in(node.right)
    return set()


def generate_factor_candidates(
    seeds: list[FactorSeed],
    *,
    field_types: dict[str, str],
    config: GenerationConfig | None = None,
) -> list[GeneratedFactorCandidate]:
    settings = config or GenerationConfig()
    if settings.maxCandidates <= 0:
        raise ValueError("maxCandidates must be positive")
    normalized_field_types = {
        canonical_field_name(name): field_type for name, field_type in field_types.items()
    }
    valid_seeds: list[tuple[FactorSeed, Expression]] = []
    seed_expression_ids: set[str] = set()
    for seed in sorted(seeds, key=lambda item: item.factorId):
        canonical = canonicalize(seed.expressionAst)
        if not validate_factor_expression(canonical, field_types=normalized_field_types).valid:
            continue
        valid_seeds.append((seed, canonical))
        seed_expression_ids.add(expression_id(canonical))

    emitted: dict[str, GeneratedFactorCandidate] = {}

    def emit(candidate: GeneratedFactorCandidate) -> None:
        if candidate.expressionId in seed_expression_ids or candidate.expressionId in emitted:
            return
        validation = validate_factor_expression(
            candidate.expressionAst,
            field_types=normalized_field_types,
        )
        if validation.valid:
            emitted[candidate.expressionId] = candidate

    for seed, expression in valid_seeds:
        for window in sorted(set(settings.allowedWindows)):
            if window <= 0:
                continue
            mutated = canonicalize(_replace_windows(expression, window))
            emit(
                GeneratedFactorCandidate.from_expression(
                    parentIds=(seed.factorId,),
                    mutationType="window",
                    expression=mutated,
                    mutationDetail={"window": window},
                )
            )
        present_fields = _fields_in(expression)
        for source, targets in sorted(settings.fieldReplacements.items()):
            normalized_source = canonical_field_name(source)
            if normalized_source not in present_fields:
                continue
            for target in sorted(set(targets)):
                normalized_target = canonical_field_name(target)
                if normalized_target not in normalized_field_types:
                    continue
                if normalized_field_types.get(normalized_source) != normalized_field_types[normalized_target]:
                    continue
                emit(
                    GeneratedFactorCandidate.from_expression(
                        parentIds=(seed.factorId,),
                        mutationType="field",
                        expression=_replace_field(expression, normalized_source, normalized_target),
                        mutationDetail={"source": normalized_source, "target": normalized_target},
                    )
                )

    for left_index, (left_seed, left_expression) in enumerate(valid_seeds):
        for right_seed, right_expression in valid_seeds[left_index + 1 :]:
            for operator in settings.crossOperators:
                if operator not in {"safe_add", "safe_multiply"}:
                    continue
                emit(
                    GeneratedFactorCandidate.from_expression(
                        parentIds=(left_seed.factorId, right_seed.factorId),
                        mutationType="cross",
                        expression=FunctionCall(operator, (left_expression, right_expression)),
                        mutationDetail={"operator": operator},
                    )
                )

    return sorted(emitted.values(), key=lambda item: item.candidateId)[: settings.maxCandidates]
