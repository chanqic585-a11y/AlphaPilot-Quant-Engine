"""Collapse canonical expression duplicates before expensive evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from .generator import GeneratedFactorCandidate


@dataclass(frozen=True)
class SemanticDeduplicationResult:
    uniqueCandidates: list[GeneratedFactorCandidate]
    duplicateMap: dict[str, str]
    duplicateCount: int


def deduplicate_candidates(
    candidates: list[GeneratedFactorCandidate],
) -> SemanticDeduplicationResult:
    by_expression: dict[str, GeneratedFactorCandidate] = {}
    duplicate_map: dict[str, str] = {}
    for candidate in sorted(candidates, key=lambda item: item.candidateId):
        existing = by_expression.get(candidate.expressionId)
        if existing is None:
            by_expression[candidate.expressionId] = candidate
        else:
            duplicate_map[candidate.candidateId] = existing.candidateId
    unique = sorted(by_expression.values(), key=lambda item: item.candidateId)
    return SemanticDeduplicationResult(
        uniqueCandidates=unique,
        duplicateMap=duplicate_map,
        duplicateCount=len(duplicate_map),
    )
