"""Development-only ranking for event-window candidate triage."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Sequence

from .workflow_candidates import ShortCycleWorkflowCandidate


@dataclass(frozen=True)
class CandidatePrescreenMetrics:
    candidateKey: str
    timeframe: str
    signalFamily: str
    tradeCount: int
    profitFactor: float | None
    averageNetR: float | None
    totalR: float
    maximumDrawdownR: float
    pairCount: int
    largestPairShare: float
    eventsPer1000Candles: float


@dataclass(frozen=True)
class RejectedCandidate:
    candidateKey: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PrescreenSelection:
    selected: tuple[ShortCycleWorkflowCandidate, ...]
    rejected: tuple[RejectedCandidate, ...]


def rejection_reasons(metrics: CandidatePrescreenMetrics) -> tuple[str, ...]:
    reasons: list[str] = []
    if metrics.tradeCount < 30:
        reasons.append("insufficient_development_sample")
    if metrics.averageNetR is None or metrics.averageNetR <= 0:
        reasons.append("non_positive_cost_adjusted_expectancy")
    if metrics.profitFactor is None or metrics.profitFactor <= 1.0:
        reasons.append("profit_factor_not_above_one")
    if metrics.maximumDrawdownR > max(25.0, abs(metrics.totalR) * 1.5):
        reasons.append("development_drawdown_inefficient")
    if metrics.pairCount < 5 or metrics.largestPairShare > 0.5:
        reasons.append("symbol_concentration_too_high")
    if metrics.eventsPer1000Candles > 12.0:
        reasons.append("event_frequency_too_high")
    return tuple(reasons)


def _score(metrics: CandidatePrescreenMetrics) -> tuple[float, float, float, int, str]:
    profit_factor = float(metrics.profitFactor or 0.0)
    expectancy = float(metrics.averageNetR or 0.0)
    drawdown_efficiency = metrics.totalR / max(metrics.maximumDrawdownR, 1.0)
    return (
        expectancy,
        profit_factor,
        drawdown_efficiency,
        metrics.pairCount,
        metrics.candidateKey,
    )


def select_prescreen_candidates(
    candidates: Sequence[ShortCycleWorkflowCandidate],
    metrics: Iterable[CandidatePrescreenMetrics],
    *,
    per_timeframe: int = 5,
    max_per_family: int = 2,
) -> PrescreenSelection:
    metric_by_key = {item.candidateKey: item for item in metrics}
    rejected: list[RejectedCandidate] = []
    selected: list[ShortCycleWorkflowCandidate] = []

    for timeframe in ("5m", "15m"):
        eligible: list[tuple[ShortCycleWorkflowCandidate, CandidatePrescreenMetrics]] = []
        for candidate in candidates:
            if candidate.timeframe != timeframe:
                continue
            candidate_metrics = metric_by_key.get(candidate.familyKey)
            if candidate_metrics is None:
                rejected.append(RejectedCandidate(candidate.familyKey, ("metrics_missing",)))
                continue
            reasons = rejection_reasons(candidate_metrics)
            if reasons:
                rejected.append(RejectedCandidate(candidate.familyKey, reasons))
                continue
            eligible.append((candidate, candidate_metrics))

        family_counts: Counter[str] = Counter()
        for candidate, candidate_metrics in sorted(
            eligible, key=lambda item: _score(item[1]), reverse=True
        ):
            if len([item for item in selected if item.timeframe == timeframe]) >= per_timeframe:
                rejected.append(RejectedCandidate(candidate.familyKey, ("rank_below_cutoff",)))
                continue
            if family_counts[candidate.signalFamily] >= max_per_family:
                rejected.append(RejectedCandidate(candidate.familyKey, ("family_diversity_cap",)))
                continue
            selected.append(candidate)
            family_counts[candidate.signalFamily] += 1

        selected_count = sum(item.timeframe == timeframe for item in selected)
        if selected_count != per_timeframe:
            raise ValueError(
                f"event_window_prescreen_insufficient_eligible:{timeframe}:{selected_count}/{per_timeframe}"
            )

    return PrescreenSelection(tuple(selected), tuple(rejected))
