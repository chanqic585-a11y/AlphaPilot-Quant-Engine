"""Frozen, multi-dimensional similarity policy for research artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


@dataclass(frozen=True)
class ArtifactSimilarityPolicy:
    frozenAt: str
    exactCorrelation: float
    familyCorrelation: float
    familyEventOverlap: float
    policyHash: str

    @classmethod
    def frozen_default(cls, frozen_at: str) -> "ArtifactSimilarityPolicy":
        payload = {
            "frozenAt": frozen_at,
            "exactCorrelation": 0.99,
            "familyCorrelation": 0.90,
            "familyEventOverlap": 0.75,
        }
        return cls(**payload, policyHash=stable_hash(payload, prefix="similarity_policy"))


@dataclass(frozen=True)
class SimilarityEvidence:
    sourceLineageMatch: bool
    canonicalFormulaMatch: bool
    semanticMechanismMatch: bool
    signalCorrelation: float | None
    eventOverlap: float | None
    dailyReturnCorrelation: float | None
    holdingOverlap: float | None
    parameterLineageMatch: bool


@dataclass(frozen=True)
class SimilarityDecision:
    classification: str
    supportingDimensions: tuple[str, ...]
    policyHash: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["supportingDimensions"] = list(self.supportingDimensions)
        return result


def _at_least(value: float | None, threshold: float) -> bool:
    return value is not None and value >= threshold


def classify_similarity(
    evidence: SimilarityEvidence, policy: ArtifactSimilarityPolicy
) -> SimilarityDecision:
    dimensions: list[str] = []
    for name, value in asdict(evidence).items():
        if value is True or (isinstance(value, float) and value >= policy.familyEventOverlap):
            dimensions.append(name)
    exact = evidence.sourceLineageMatch and evidence.canonicalFormulaMatch
    exact = exact or (
        _at_least(evidence.signalCorrelation, policy.exactCorrelation)
        and _at_least(evidence.dailyReturnCorrelation, policy.exactCorrelation)
        and _at_least(evidence.eventOverlap, policy.exactCorrelation)
    )
    near_duplicate = (
        evidence.semanticMechanismMatch
        and _at_least(evidence.signalCorrelation, policy.exactCorrelation)
        and _at_least(evidence.dailyReturnCorrelation, policy.exactCorrelation)
        and _at_least(evidence.eventOverlap, policy.familyEventOverlap)
    )
    same_family = (
        evidence.semanticMechanismMatch
        and _at_least(evidence.signalCorrelation, policy.familyCorrelation)
        and _at_least(evidence.eventOverlap, policy.familyEventOverlap)
        and (
            evidence.parameterLineageMatch
            or _at_least(evidence.dailyReturnCorrelation, policy.familyCorrelation)
        )
    )
    if exact:
        classification = "exact_duplicate"
    elif near_duplicate:
        classification = "near_duplicate"
    elif same_family:
        classification = "same_family_variant"
    elif evidence.semanticMechanismMatch:
        classification = "mechanism_related"
    else:
        classification = "independent"
    return SimilarityDecision(classification, tuple(sorted(dimensions)), policy.policyHash)
