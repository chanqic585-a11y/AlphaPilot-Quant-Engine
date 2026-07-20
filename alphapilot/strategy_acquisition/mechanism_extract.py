"""Create source-backed artifacts without inventing formulas or rules."""

from __future__ import annotations

from typing import Any

from .models import SourceEvidence, StrategyArtifact
from .source_equivalence import SOURCE_EQUIVALENCE_CLASSES


class FormulaHallucinationBlocked(ValueError):
    pass


def build_extracted_artifact(
    *,
    artifactId: str,
    artifactType: str,
    name: str,
    familyId: str,
    authorityRef: str,
    sourceIds: tuple[str, ...],
    sourceHashes: tuple[str, ...],
    licenseClass: str,
    sourceEquivalenceClass: str,
    marketMechanism: str,
    formula: str | None,
    requiredFields: tuple[str, ...],
    universe: tuple[str, ...],
    timeframe: str,
    entryRules: tuple[str, ...],
    exitRules: tuple[str, ...],
    positionSizing: str,
    riskManagement: str,
    dataProfile: dict[str, Any],
    evidence: tuple[SourceEvidence, ...],
) -> StrategyArtifact:
    if sourceEquivalenceClass not in SOURCE_EQUIVALENCE_CLASSES:
        raise ValueError(f"unsupported source equivalence: {sourceEquivalenceClass}")
    if not authorityRef.strip():
        raise ValueError("authorityRef is required because this store is projection-only")
    has_extractable_rules = bool(formula or entryRules or exitRules)
    valid_evidence = tuple(
        item
        for item in evidence
        if item.sourceId in sourceIds
        and item.sourceHash in sourceHashes
        and item.sourcePath.strip()
        and item.locator.strip()
        and 0.0 <= item.extractionConfidence <= 1.0
    )
    if has_extractable_rules and not valid_evidence:
        raise FormulaHallucinationBlocked(
            "formula_hallucination_blocked: formula/rules require source locator evidence"
        )
    return StrategyArtifact(
        artifactId=artifactId,
        artifactType=artifactType,
        name=name,
        familyId=familyId,
        authorityRef=authorityRef,
        sourceIds=sourceIds,
        sourceHashes=sourceHashes,
        licenseClass=licenseClass,
        sourceEquivalenceClass=sourceEquivalenceClass,
        marketMechanism=marketMechanism,
        formula=formula,
        requiredFields=requiredFields,
        universe=universe,
        timeframe=timeframe,
        entryRules=entryRules,
        exitRules=exitRules,
        positionSizing=positionSizing,
        riskManagement=riskManagement,
        dataProfile=dict(dataProfile),
        evidence=valid_evidence,
    )
