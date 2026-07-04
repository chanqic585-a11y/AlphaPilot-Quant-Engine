"""Build coarsened probability bucket tables for V13.4.19 research.

The implementation reads the existing V13.4.14 score table and aggregates
bucket-level rows. Because the full raw probability sample dataset is not
committed, profit factor is a sample-count weighted bucket-level approximation,
not a raw win/loss recomputation.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from alphapilot.probability.probability_bucket_coverage import (
    current_gate_pass,
    exploratory_gate_pass,
    research_gate_pass,
    round_optional,
    safe_float,
    safe_int,
)

CoarseningKeyBuilder = Callable[[dict[str, Any]], tuple[tuple[str, str], ...]]


def _rsi_coarse(value: Any) -> str:
    raw = str(value or "unavailable")
    if raw in {"below30", "30-45"}:
        return "low"
    if raw == "45-55":
        return "middle"
    if raw in {"55-65", "above65"}:
        return "high"
    return "unavailable"


def _ema_coarse(value: Any) -> str:
    raw = str(value or "unavailable")
    if raw in {"below_ema20", "near_ema20", "above_ema20"}:
        return "near_or_below"
    if raw == "extended_above_ema20":
        return "extended"
    return "unavailable"


def _bb_coarse(value: Any) -> str:
    raw = str(value or "unavailable")
    if raw in {"lower", "middle"}:
        return "lower_or_middle"
    if raw in {"upper", "outside"}:
        return "upper_or_outside"
    return "unavailable"


def _module_type(row: dict[str, Any]) -> str:
    regime = str(row.get("regimeCandidate") or "unknown")
    if regime == "trend":
        return "trend_module"
    if regime == "mean_reversion":
        return "mean_reversion_module"
    return "no_entry_module"


def scheme_a_key(row: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return (
        ("regimeCandidate", str(row.get("regimeCandidate") or "unknown")),
        ("liquidityBucket", str(row.get("liquidityBucket") or "unavailable")),
        ("volatilityBucket", str(row.get("volatilityBucket") or "unavailable")),
        ("rsiBucket", str(row.get("rsiBucket") or "unavailable")),
        ("emaDistanceBucket", str(row.get("emaDistanceBucket") or "unavailable")),
        ("bbPositionBucket", str(row.get("bbPositionBucket") or "unavailable")),
        ("btcState", str(row.get("btcState") or "unknown")),
    )


def scheme_b_key(row: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return (
        ("regimeCandidate", str(row.get("regimeCandidate") or "unknown")),
        ("liquidityBucket", str(row.get("liquidityBucket") or "unavailable")),
        ("volatilityBucket", str(row.get("volatilityBucket") or "unavailable")),
        ("rsiBucketCoarse", _rsi_coarse(row.get("rsiBucket"))),
        ("emaDistanceBucketCoarse", _ema_coarse(row.get("emaDistanceBucket"))),
        ("bbPositionBucketCoarse", _bb_coarse(row.get("bbPositionBucket"))),
        ("btcState", str(row.get("btcState") or "unknown")),
    )


def scheme_c_key(row: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return (
        ("regimeCandidate", str(row.get("regimeCandidate") or "unknown")),
        ("liquidityBucket", str(row.get("liquidityBucket") or "unavailable")),
        ("btcState", str(row.get("btcState") or "unknown")),
    )


def scheme_d_key(row: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return (
        ("regimeCandidate", str(row.get("regimeCandidate") or "unknown")),
        ("moduleType", _module_type(row)),
        ("volatilityBucket", str(row.get("volatilityBucket") or "unavailable")),
        ("btcState", str(row.get("btcState") or "unknown")),
    )


COARSENING_SCHEMES: dict[str, dict[str, Any]] = {
    "coarse_a_remove_time": {
        "description": "Remove time buckets. V13.4.14 table has no time fields, so this is a same-dimension baseline.",
        "keyBuilder": scheme_a_key,
        "warnings": ["timeOfDay/dayOfWeek fields are not present in V13.4.14 score table."],
    },
    "coarse_b_merge_rsi_ema_bb": {
        "description": "Merge RSI into low/middle/high, EMA distance into near_or_below/extended, and Bollinger position into two coarse zones.",
        "keyBuilder": scheme_b_key,
        "warnings": [],
    },
    "coarse_c_regime_liquidity_btc": {
        "description": "Keep only regime, liquidity, and BTC state to test broad statistical structure.",
        "keyBuilder": scheme_c_key,
        "warnings": [],
    },
    "coarse_d_regime_module_volatility": {
        "description": "Keep regime, derived module type, volatility, and BTC state.",
        "keyBuilder": scheme_d_key,
        "warnings": ["moduleType is derived from regimeCandidate because V13.4.14 table does not store moduleType."],
    },
}


def _bucket_id(parts: tuple[tuple[str, str], ...]) -> str:
    return "_".join(value for _, value in parts)


def _empty_aggregate(parts: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    return {
        "bucketId": _bucket_id(parts),
        "dimensions": dict(parts),
        "sampleCount": 0,
        "_tpWeighted": 0.0,
        "_slWeighted": 0.0,
        "_mfeWeighted": 0.0,
        "_mfeWeight": 0,
        "_maeWeighted": 0.0,
        "_maeWeight": 0,
        "_expectancyWeighted": 0.0,
        "_expectancyWeight": 0,
        "_profitFactorWeighted": 0.0,
        "_profitFactorWeight": 0,
        "sourceBucketCount": 0,
        "sourceBuckets": [],
    }


def _add_metric_weight(target: dict[str, Any], row: dict[str, Any], source_key: str, sum_key: str, weight_key: str) -> None:
    value = safe_float(row.get(source_key))
    count = safe_int(row.get("sampleCount"))
    if value is None or count <= 0:
        return
    target[sum_key] += value * count
    target[weight_key] += count


def _finalize_aggregate(row: dict[str, Any]) -> dict[str, Any]:
    count = safe_int(row.get("sampleCount"))
    hit_tp = row["_tpWeighted"] / count if count > 0 else None
    hit_sl = row["_slWeighted"] / count if count > 0 else None
    mfe = row["_mfeWeighted"] / row["_mfeWeight"] if row["_mfeWeight"] else None
    mae = row["_maeWeighted"] / row["_maeWeight"] if row["_maeWeight"] else None
    expectancy = row["_expectancyWeighted"] / row["_expectancyWeight"] if row["_expectancyWeight"] else None
    profit_factor = row["_profitFactorWeighted"] / row["_profitFactorWeight"] if row["_profitFactorWeight"] else None
    payload = {
        "bucketId": row["bucketId"],
        **row["dimensions"],
        "sampleCount": count,
        "hitTpBeforeSlProbability": round_optional(hit_tp),
        "hitSlBeforeTpProbability": round_optional(hit_sl),
        "averageMfePct": round_optional(mfe, 8),
        "averageMaePct": round_optional(mae, 8),
        "averageReturnPct": round_optional(expectancy, 8),
        "profitFactor": round_optional(profit_factor),
        "expectancy": round_optional(expectancy, 8),
        "sourceBucketCount": row["sourceBucketCount"],
        "profitFactorAggregation": "sample_count_weighted_bucket_level_approximation",
        "profitFactorAvailableSampleCount": row["_profitFactorWeight"],
        "sourceBuckets": sorted(row["sourceBuckets"])[:25],
    }
    if current_gate_pass(payload):
        payload["confidenceLevel"] = "current_gate_candidate_research_only"
        payload["decision"] = "research_candidate_not_strategy_wired"
    elif research_gate_pass(payload):
        payload["confidenceLevel"] = "research_gate_candidate"
        payload["decision"] = "research_candidate_not_strategy_wired"
    elif exploratory_gate_pass(payload):
        payload["confidenceLevel"] = "exploratory_gate_candidate"
        payload["decision"] = "exploratory_only"
    elif count < 30:
        payload["confidenceLevel"] = "insufficient_sample"
        payload["decision"] = "observe_only"
    else:
        payload["confidenceLevel"] = "observe_only"
        payload["decision"] = "observe_only"
    return payload


def coarsen_probability_table(
    rows: list[dict[str, Any]],
    key_builder: CoarseningKeyBuilder,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[tuple[str, str], ...], dict[str, Any]] = {}
    for source_row in rows:
        parts = key_builder(source_row)
        target = grouped.setdefault(parts, _empty_aggregate(parts))
        count = safe_int(source_row.get("sampleCount"))
        target["sampleCount"] += count
        target["sourceBucketCount"] += 1
        target["sourceBuckets"].append(str(source_row.get("bucketId") or "unknown"))
        if source_row.get("hitTpBeforeSlProbability") is not None:
            target["_tpWeighted"] += (safe_float(source_row.get("hitTpBeforeSlProbability")) or 0.0) * count
        if source_row.get("hitSlBeforeTpProbability") is not None:
            target["_slWeighted"] += (safe_float(source_row.get("hitSlBeforeTpProbability")) or 0.0) * count
        _add_metric_weight(target, source_row, "averageMfePct", "_mfeWeighted", "_mfeWeight")
        _add_metric_weight(target, source_row, "averageMaePct", "_maeWeighted", "_maeWeight")
        _add_metric_weight(target, source_row, "expectancy", "_expectancyWeighted", "_expectancyWeight")
        _add_metric_weight(target, source_row, "profitFactor", "_profitFactorWeighted", "_profitFactorWeight")

    finalized = [_finalize_aggregate(row) for row in grouped.values()]
    return sorted(
        finalized,
        key=lambda row: (
            row["decision"] == "observe_only",
            -(safe_float(row.get("expectancy")) or -999.0),
            -(safe_float(row.get("profitFactor")) or -999.0),
            -safe_int(row.get("sampleCount")),
            row["bucketId"],
        ),
    )


def build_all_coarsened_tables(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for scheme_id, scheme in COARSENING_SCHEMES.items():
        tables[scheme_id] = coarsen_probability_table(rows, scheme["keyBuilder"])
    return tables
