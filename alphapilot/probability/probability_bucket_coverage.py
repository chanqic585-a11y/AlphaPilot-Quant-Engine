"""Coverage and gate helpers for V13.4.19 probability bucket research.

These helpers operate on existing local probability table artifacts only. They
do not alter strategy entry logic, run backtests, enter Dry-run, or connect to
any exchange permission.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


CURRENT_GATE = {
    "sampleCountGte": 50,
    "hitTpBeforeSlProbabilityGte": 0.45,
    "profitFactorGte": 1.2,
    "expectancyGt": 0.0,
    "usage": "historical validation gate only; not a live trading permission",
}

RESEARCH_GATE = {
    "sampleCountGte": 50,
    "profitFactorGte": 1.1,
    "expectancyGt": 0.0,
    "usage": "researchGate is not used for trading",
}

EXPLORATORY_GATE = {
    "sampleCountGte": 30,
    "profitFactorGt": 1.0,
    "usage": "exploratoryGate is for analysis only; do not connect to strategy entry",
}


def safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def round_optional(value: Any, digits: int = 6) -> float | None:
    raw = safe_float(value)
    return None if raw is None else round(raw, digits)


def current_gate_pass(row: dict[str, Any]) -> bool:
    return (
        safe_int(row.get("sampleCount")) >= CURRENT_GATE["sampleCountGte"]
        and (safe_float(row.get("hitTpBeforeSlProbability")) or 0.0) >= CURRENT_GATE["hitTpBeforeSlProbabilityGte"]
        and (safe_float(row.get("profitFactor")) or 0.0) >= CURRENT_GATE["profitFactorGte"]
        and (safe_float(row.get("expectancy")) or 0.0) > CURRENT_GATE["expectancyGt"]
    )


def research_gate_pass(row: dict[str, Any]) -> bool:
    return (
        safe_int(row.get("sampleCount")) >= RESEARCH_GATE["sampleCountGte"]
        and (safe_float(row.get("profitFactor")) or 0.0) >= RESEARCH_GATE["profitFactorGte"]
        and (safe_float(row.get("expectancy")) or 0.0) > RESEARCH_GATE["expectancyGt"]
    )


def exploratory_gate_pass(row: dict[str, Any]) -> bool:
    return (
        safe_int(row.get("sampleCount")) >= EXPLORATORY_GATE["sampleCountGte"]
        and (safe_float(row.get("profitFactor")) or 0.0) > EXPLORATORY_GATE["profitFactorGt"]
    )


def gate_failure_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    sample_count = safe_int(row.get("sampleCount"))
    hit_probability = safe_float(row.get("hitTpBeforeSlProbability"))
    profit_factor = safe_float(row.get("profitFactor"))
    expectancy = safe_float(row.get("expectancy"))
    if sample_count < CURRENT_GATE["sampleCountGte"]:
        reasons.append("sample_count_below_50")
    if hit_probability is None or hit_probability < CURRENT_GATE["hitTpBeforeSlProbabilityGte"]:
        reasons.append("hit_probability_below_0_45")
    if profit_factor is None or profit_factor < CURRENT_GATE["profitFactorGte"]:
        reasons.append("profit_factor_below_1_2")
    if expectancy is None or expectancy <= CURRENT_GATE["expectancyGt"]:
        reasons.append("expectancy_not_positive")
    return reasons


def summarize_gate_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failure_reasons: Counter[str] = Counter()
    weighted_failure_reasons: Counter[str] = Counter()
    for row in rows:
        reasons = gate_failure_reasons(row)
        for reason in reasons:
            failure_reasons[reason] += 1
            weighted_failure_reasons[reason] += safe_int(row.get("sampleCount"))

    return {
        "bucketCount": len(rows),
        "totalSampleCount": sum(safe_int(row.get("sampleCount")) for row in rows),
        "sufficientSampleBucketCount": sum(
            1 for row in rows if safe_int(row.get("sampleCount")) >= CURRENT_GATE["sampleCountGte"]
        ),
        "pfGt1BucketCount": sum(
            1 for row in rows if (safe_float(row.get("profitFactor")) or 0.0) > 1.0
        ),
        "pfGte1_2BucketCount": sum(
            1 for row in rows if (safe_float(row.get("profitFactor")) or 0.0) >= 1.2
        ),
        "expectancyGt0BucketCount": sum(
            1 for row in rows if (safe_float(row.get("expectancy")) or 0.0) > 0.0
        ),
        "hitProbabilityGte0_45BucketCount": sum(
            1 for row in rows if (safe_float(row.get("hitTpBeforeSlProbability")) or 0.0) >= 0.45
        ),
        "currentGatePassBucketCount": sum(1 for row in rows if current_gate_pass(row)),
        "researchGatePassBucketCount": sum(1 for row in rows if research_gate_pass(row)),
        "exploratoryGatePassBucketCount": sum(1 for row in rows if exploratory_gate_pass(row)),
        "currentGate": CURRENT_GATE,
        "researchGate": RESEARCH_GATE,
        "exploratoryGate": EXPLORATORY_GATE,
        "failureReasonBucketCounts": dict(sorted(failure_reasons.items())),
        "failureReasonWeightedSampleCounts": dict(sorted(weighted_failure_reasons.items())),
    }


def top_research_buckets(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    candidates = [row for row in rows if research_gate_pass(row)]
    ordered = sorted(
        candidates,
        key=lambda row: (
            safe_float(row.get("expectancy")) or -999.0,
            safe_float(row.get("profitFactor")) or -999.0,
            safe_int(row.get("sampleCount")),
        ),
        reverse=True,
    )
    return ordered[:limit]


def top_exploratory_buckets(rows: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    candidates = [row for row in rows if exploratory_gate_pass(row)]
    ordered = sorted(
        candidates,
        key=lambda row: (
            safe_float(row.get("expectancy")) or -999.0,
            safe_float(row.get("profitFactor")) or -999.0,
            safe_int(row.get("sampleCount")),
        ),
        reverse=True,
    )
    return ordered[:limit]
