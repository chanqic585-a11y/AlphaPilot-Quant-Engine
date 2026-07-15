"""Exact trade-identity and narrowly-tolerated numerical parity checks."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


IDENTITY_FIELDS = (
    "signalId",
    "symbol",
    "direction",
    "decisionBar",
    "entryBar",
    "exitTimestamp",
    "exitReasonClass",
)

NUMERIC_FIELDS = (
    "entryPrice",
    "exitPrice",
    "grossR",
    "feesR",
    "fundingR",
    "slippageR",
    "netR",
)


def _identity(row: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "") for field in IDENTITY_FIELDS)


def _identity_text(identity: tuple[str, ...]) -> str:
    return "|".join(identity)


def evaluate_translation_parity(
    reference_trades: Sequence[Mapping[str, Any]],
    implementation_trades: Sequence[Mapping[str, Any]],
    *,
    numeric_tolerances: Mapping[str, float] | None = None,
    difference_explanations: Mapping[str, str] | None = None,
    minimum_numeric_ratio: float = 0.99,
) -> dict[str, Any]:
    tolerances = {field: 1e-9 for field in NUMERIC_FIELDS}
    tolerances.update({key: float(value) for key, value in (numeric_tolerances or {}).items()})
    if any(field not in NUMERIC_FIELDS for field in tolerances):
        raise ValueError("numeric tolerance may only target approved numerical fields")
    explanations = dict(difference_explanations or {})
    reference = {_identity(row): dict(row) for row in reference_trades}
    implementation = {_identity(row): dict(row) for row in implementation_trades}
    matched = sorted(set(reference) & set(implementation))
    missing = sorted(set(reference) - set(implementation))
    extra = sorted(set(implementation) - set(reference))
    denominator = max(len(reference), len(implementation), 1)
    identity_ratio = len(matched) / denominator

    comparisons = 0
    within = 0
    outside: list[dict[str, Any]] = []
    for identity in matched:
        for field in NUMERIC_FIELDS:
            comparisons += 1
            left = float(reference[identity].get(field) or 0.0)
            right = float(implementation[identity].get(field) or 0.0)
            difference = abs(left - right)
            key = f"{_identity_text(identity)}|{field}"
            if difference <= tolerances[field]:
                within += 1
            else:
                outside.append(
                    {
                        "identity": _identity_text(identity),
                        "field": field,
                        "difference": difference,
                        "tolerance": tolerances[field],
                        "explanation": explanations.get(key),
                    }
                )
    numeric_ratio = within / comparisons if comparisons else 1.0
    unexplained = [row for row in outside if not row["explanation"]]
    passed = (
        identity_ratio == 1.0
        and not missing
        and not extra
        and numeric_ratio >= minimum_numeric_ratio
        and not unexplained
    )
    return {
        "schemaVersion": "translation_parity_v2",
        "identityFields": list(IDENTITY_FIELDS),
        "numericFields": list(NUMERIC_FIELDS),
        "identityMatchRatio": identity_ratio,
        "numericWithinToleranceRatio": numeric_ratio,
        "missingTradeIdentities": [_identity_text(value) for value in missing],
        "extraTradeIdentities": [_identity_text(value) for value in extra],
        "outsideTolerance": outside,
        "unexplainedDifferenceCount": len(unexplained),
        "translationParityPassed": passed,
    }
