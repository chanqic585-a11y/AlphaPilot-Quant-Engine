"""Chronological, no-lookahead portfolio replay for frozen rescue policies."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Iterable, Mapping

import pandas as pd

from alphapilot.demo_release_replay.adapters import canonical_metrics

from .contracts import RiskPolicy


@dataclass(frozen=True)
class PolicyReplayResult:
    policy: RiskPolicy
    accepted_trades: tuple[dict[str, Any], ...]
    rejected_trades: tuple[dict[str, Any], ...]
    rejection_counts: Mapping[str, int]
    metrics: Mapping[str, Any]
    stress_metrics: Mapping[str, Mapping[str, Any]]
    sleeve_attribution: Mapping[str, Mapping[str, Any]]
    monthly_consistency: Mapping[str, Any]
    status: str = "development_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "acceptedTradeCount": len(self.accepted_trades),
            "formalCandidateCount": 0,
            "lockedOosReadCount": 0,
            "metrics": dict(self.metrics),
            "monthlyConsistency": dict(self.monthly_consistency),
            "policy": self.policy.to_dict(),
            "rejectedTradeCount": len(self.rejected_trades),
            "rejectionCounts": dict(self.rejection_counts),
            "releaseCount": 0,
            "sleeveAttribution": {
                key: dict(value) for key, value in self.sleeve_attribution.items()
            },
            "status": self.status,
            "stressMetrics": {key: dict(value) for key, value in self.stress_metrics.items()},
        }


def _dated(row: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(row)
    output["_entry"] = pd.Timestamp(row["entryDate"])
    output["_exit"] = pd.Timestamp(row["exitDate"])
    if output["_entry"].tzinfo is None:
        output["_entry"] = output["_entry"].tz_localize("UTC")
    if output["_exit"].tzinfo is None:
        output["_exit"] = output["_exit"].tz_localize("UTC")
    return output


def _clean(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _stress_metrics(trades: tuple[dict[str, Any], ...], cost_r: float) -> dict[str, Any]:
    stressed = [{**row, "netR": float(row["netR"]) - cost_r} for row in trades]
    return canonical_metrics(stressed)


def _sleeve_attribution(trades: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in trades:
        grouped[str(row["candidateId"])].append(row)
    return {key: canonical_metrics(value) for key, value in sorted(grouped.items())}


def _monthly_consistency(trades: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    monthly: dict[str, float] = defaultdict(float)
    for row in trades:
        month = pd.Timestamp(row["entryDate"]).strftime("%Y-%m")
        monthly[month] += float(row["netR"])
    values = list(monthly.values())
    positive = sum(value > 0 for value in values)
    return {
        "activeMonthCount": len(values),
        "bestMonthR": round(max(values), 6) if values else None,
        "monthlyNetR": {key: round(value, 6) for key, value in sorted(monthly.items())},
        "positiveMonthCount": positive,
        "positiveMonthRatio": positive / len(values) if values else None,
        "worstMonthR": round(min(values), 6) if values else None,
    }


def replay_policy(trades: Iterable[Mapping[str, Any]], policy: RiskPolicy) -> PolicyReplayResult:
    ordered = sorted(
        (_dated(row) for row in trades),
        key=lambda row: (row["_entry"], str(row.get("candidateId")), str(row.get("pair"))),
    )
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()

    for candidate in ordered:
        entry = candidate["_entry"]
        pair = str(candidate["pair"])
        direction = str(candidate["direction"])
        completed = [row for row in accepted if row["_exit"] <= entry]
        open_positions = [row for row in accepted if row["_entry"] <= entry < row["_exit"]]

        pair_exits = [row["_exit"] for row in completed if str(row["pair"]) == pair]
        latest_pair_exit = max(pair_exits) if pair_exits else None
        losing_pair_exits = [
            row["_exit"]
            for row in completed
            if str(row["pair"]) == pair and float(row["netR"]) < 0
        ]
        latest_losing_exit = max(losing_pair_exits) if losing_pair_exits else None

        reason = None
        if latest_pair_exit is not None and entry < latest_pair_exit + timedelta(days=policy.pair_cooldown_days):
            reason = "pair_cooldown"
        elif (
            latest_losing_exit is not None
            and entry < latest_losing_exit + timedelta(days=policy.losing_pair_cooldown_days)
        ):
            reason = "losing_pair_cooldown"
        elif sum(str(row["direction"]) == direction for row in open_positions) >= policy.same_direction_cap:
            reason = "same_direction_cap"
        elif len(open_positions) >= policy.maximum_concurrent_positions:
            reason = "maximum_concurrent_positions"

        if reason:
            reasons[reason] += 1
            rejected.append({**candidate, "rejectionReason": reason})
        else:
            accepted.append(candidate)

    accepted_clean = tuple(_clean(row) for row in accepted)
    rejected_clean = tuple(_clean(row) for row in rejected)
    stress = {
        f"plus_{cost_r:.2f}R": _stress_metrics(accepted_clean, cost_r)
        for cost_r in policy.additional_cost_stress_r
    }
    return PolicyReplayResult(
        policy=policy,
        accepted_trades=accepted_clean,
        rejected_trades=rejected_clean,
        rejection_counts=dict(reasons),
        metrics=canonical_metrics(accepted_clean),
        stress_metrics=stress,
        sleeve_attribution=_sleeve_attribution(accepted_clean),
        monthly_consistency=_monthly_consistency(accepted_clean),
    )
