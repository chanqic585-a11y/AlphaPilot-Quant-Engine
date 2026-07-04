"""Aggregate probability candidate samples into condition score buckets."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from alphapilot.probability.condition_buckets import bucket_id, round_optional, safe_float
from alphapilot.probability.probability_schema import ProbabilityBucketRow, ProbabilityCandidateSample


def _profit_factor(outcomes: list[float]) -> float | None:
    wins = sum(value for value in outcomes if value > 0)
    losses = abs(sum(value for value in outcomes if value < 0))
    if losses == 0:
        return None
    return round(wins / losses, 6)


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 8)


def _confidence_level(sample_count: int, tp_probability: float | None, profit_factor: float | None, expectancy: float | None, minimum_samples: int) -> str:
    if sample_count < minimum_samples:
        return "insufficient_sample"
    if (
        tp_probability is not None
        and profit_factor is not None
        and expectancy is not None
        and tp_probability >= 0.45
        and profit_factor >= 1.2
        and expectancy > 0
    ):
        return "research_promising"
    return "observe_only"


def _decision(confidence_level: str) -> str:
    return "research_candidate" if confidence_level == "research_promising" else "observe_only"


def _sample_bucket_key(sample: ProbabilityCandidateSample) -> tuple[str, str, str, str, str, str, str]:
    return (
        sample.regimeCandidate,
        sample.liquidityBucket,
        sample.volatilityBucket,
        sample.rsiBucket,
        sample.distanceToEma20Bucket,
        sample.distanceToBollingerBucket,
        sample.btcState,
    )


def build_probability_score_table(
    samples: list[ProbabilityCandidateSample],
    primary_window: int,
    minimum_samples: int = 50,
) -> list[ProbabilityBucketRow]:
    grouped: dict[tuple[str, str, str, str, str, str, str], list[ProbabilityCandidateSample]] = defaultdict(list)
    for sample in samples:
        if str(primary_window) in sample.labels:
            grouped[_sample_bucket_key(sample)].append(sample)

    rows: list[ProbabilityBucketRow] = []
    for key, bucket_samples in grouped.items():
        labels = [sample.labels[str(primary_window)] for sample in bucket_samples]
        sample_count = len(labels)
        tp_count = sum(1 for label in labels if label.hitTpBeforeSl)
        sl_count = sum(1 for label in labels if label.hitSlBeforeTp)
        outcomes = [value for value in (safe_float(label.outcomeReturnPct) for label in labels) if value is not None]
        mfe_values = [value for value in (safe_float(label.mfePct) for label in labels) if value is not None]
        mae_values = [value for value in (safe_float(label.maePct) for label in labels) if value is not None]

        tp_probability = round(tp_count / sample_count, 6) if sample_count else None
        sl_probability = round(sl_count / sample_count, 6) if sample_count else None
        profit_factor = _profit_factor(outcomes)
        expectancy = _avg(outcomes)
        confidence = _confidence_level(sample_count, tp_probability, profit_factor, expectancy, minimum_samples)

        rows.append(
            ProbabilityBucketRow(
                bucketId=bucket_id(list(key)),
                regimeCandidate=key[0],
                liquidityBucket=key[1],
                volatilityBucket=key[2],
                rsiBucket=key[3],
                emaDistanceBucket=key[4],
                bbPositionBucket=key[5],
                btcState=key[6],
                sampleCount=sample_count,
                hitTpBeforeSlProbability=tp_probability,
                hitSlBeforeTpProbability=sl_probability,
                averageMfePct=round_optional(_avg(mfe_values)),
                averageMaePct=round_optional(_avg(mae_values)),
                averageReturnPct=round_optional(expectancy),
                profitFactor=profit_factor,
                expectancy=round_optional(expectancy),
                confidenceLevel=confidence,
                decision=_decision(confidence),
            )
        )

    return sorted(rows, key=lambda row: (row.confidenceLevel != "research_promising", -(row.expectancy or -999), -row.sampleCount, row.bucketId))


def summarize_probability_gates(rows: list[ProbabilityBucketRow]) -> dict[str, Any]:
    passed = [row for row in rows if row.confidenceLevel == "research_promising"]
    insufficient = [row for row in rows if row.confidenceLevel == "insufficient_sample"]
    observe = [row for row in rows if row.confidenceLevel == "observe_only"]
    return {
        "totalBuckets": len(rows),
        "researchPromisingBuckets": len(passed),
        "observeOnlyBuckets": len(observe),
        "insufficientSampleBuckets": len(insufficient),
        "minimumSampleThreshold": 50,
        "passCriteria": {
            "sampleCount": ">= 50",
            "hitTpBeforeSlProbability": ">= 0.45",
            "profitFactor": ">= 1.2",
            "expectancy": "> 0",
        },
        "decisionPolicy": "insufficient samples remain observe_only and cannot approve Dry-run.",
    }


def top_positive_buckets(rows: list[ProbabilityBucketRow], limit: int = 10) -> list[dict[str, Any]]:
    candidates = [row for row in rows if row.expectancy is not None]
    ordered = sorted(candidates, key=lambda row: (row.expectancy or -999, row.sampleCount), reverse=True)
    return [row.to_dict() for row in ordered[:limit]]


def top_negative_buckets(rows: list[ProbabilityBucketRow], limit: int = 10) -> list[dict[str, Any]]:
    candidates = [row for row in rows if row.expectancy is not None]
    ordered = sorted(candidates, key=lambda row: (row.expectancy or 999, -row.sampleCount))
    return [row.to_dict() for row in ordered[:limit]]


def insufficient_sample_buckets(rows: list[ProbabilityBucketRow], limit: int = 10) -> list[dict[str, Any]]:
    candidates = [row for row in rows if row.confidenceLevel == "insufficient_sample"]
    ordered = sorted(candidates, key=lambda row: (-row.sampleCount, row.bucketId))
    return [row.to_dict() for row in ordered[:limit]]
