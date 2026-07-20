"""Frozen benchmark, cost, funding, and daily-return evidence for S01."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import math
from typing import Any, Mapping, Sequence

import pandas as pd

from .formal_portfolio import (
    replay_locked_selection,
    replay_shared_capital,
    summarize_portfolio,
)


def canonical_event_id(event: Mapping[str, Any]) -> str:
    existing = str(event.get("signalId") or "").strip()
    if existing:
        return existing
    return "|".join(
        (
            str(event.get("candidateId") or "unknown_candidate"),
            str(event.get("symbol") or "unknown_symbol"),
            str(event.get("signalIndex") if event.get("signalIndex") is not None else "na"),
            str(event.get("entryTimestamp") or "unknown_entry"),
        )
    )


def _nonfunding_cost_r(event: Mapping[str, Any]) -> float:
    components = tuple(event.get(name) for name in ("feesR", "slippageR", "spreadProxyR"))
    if any(value is not None for value in components):
        return sum(float(value or 0.0) for value in components)
    return float(event.get("costR") or 0.0)


def _scenario_event(event: Mapping[str, Any], multiplier: float) -> dict[str, Any]:
    gross_r = float(event.get("realizedGrossR") or event.get("grossR") or 0.0)
    base_cost_r = _nonfunding_cost_r(event)
    return {
        **dict(event),
        "signalId": canonical_event_id(event),
        "baseNonFundingCostR": base_cost_r,
        "costMultiplier": float(multiplier),
        "scenarioCostR": base_cost_r * float(multiplier),
        "realizedGrossR": gross_r,
        "realizedNetR": gross_r - base_cost_r * float(multiplier),
        "fundingR": event.get("fundingR"),
    }


def build_cost_stress(
    events: Sequence[Mapping[str, Any]],
    portfolio_policy: Mapping[str, Any],
    cost_model: Mapping[str, Any],
) -> dict[str, Any]:
    """Select once at base cost and reprice those same identities in stress."""

    scenario_rows = [dict(row) for row in cost_model.get("scenarios", [])]
    if not scenario_rows or str(scenario_rows[0].get("scenarioId")) != "base":
        raise ValueError("cost scenarios must begin with the frozen base scenario")
    base_events = [_scenario_event(event, 1.0) for event in events]
    base_replay = replay_shared_capital(base_events, portfolio_policy)
    base_accepted = [dict(event) for event in base_replay["accepted"]]
    accepted_ids = [canonical_event_id(event) for event in base_accepted]
    scenarios: list[dict[str, Any]] = []
    for scenario in scenario_rows:
        multiplier = float(scenario["multiplier"])
        repriced = [_scenario_event(event, multiplier) for event in base_accepted]
        replay = replay_locked_selection(repriced, portfolio_policy)
        scenarios.append(
            {
                "scenarioId": str(scenario["scenarioId"]),
                "multiplier": multiplier,
                "selectionFrozenFrom": "base",
                "acceptedEventIds": [canonical_event_id(event) for event in replay["accepted"]],
                "metrics": summarize_portfolio(replay),
                "portfolio": replay,
            }
        )
    if any(row["acceptedEventIds"] != accepted_ids for row in scenarios):
        raise RuntimeError("cost scenario changed frozen event selection")
    return {
        "schemaVersion": "s01_formal_cost_stress_v1",
        "costModel": dict(cost_model),
        "baseSelection": base_replay,
        "baseAcceptedEvents": base_accepted,
        "baseRejectedEvents": [dict(event) for event in base_replay["rejected"]],
        "selectionIdentityStable": True,
        "scenarios": scenarios,
    }


def _timestamp(value: object) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def build_funding_stress(
    events: Sequence[Mapping[str, Any]],
    *,
    adverse_rate_per_settlement: float | None,
) -> dict[str, Any]:
    """Preserve raw missing funding and optionally add a labeled proxy stress."""

    output: list[dict[str, Any]] = []
    for event in events:
        row = {**dict(event), "signalId": canonical_event_id(event)}
        row["fundingR"] = event.get("fundingR")
        if adverse_rate_per_settlement is None:
            row["conservativeFundingStressR"] = None
            row["conservativeFundingNetR"] = None
        else:
            holding_seconds = max(
                0.0,
                (_timestamp(event["exitTimestamp"]) - _timestamp(event["entryTimestamp"])).total_seconds(),
            )
            settlement_count = int(math.floor(holding_seconds / (8.0 * 60.0 * 60.0)))
            risk_distance = float(event.get("riskDistance") or 0.0)
            entry_price = float(event.get("entryPrice") or 0.0)
            notional_to_risk = entry_price / risk_distance if risk_distance > 0 else 0.0
            stress_r = abs(float(adverse_rate_per_settlement)) * settlement_count * notional_to_risk
            row["fundingSettlementCount"] = settlement_count
            row["conservativeFundingStressR"] = stress_r
            row["conservativeFundingNetR"] = float(event.get("realizedNetR") or 0.0) - stress_r
        output.append(row)
    available = adverse_rate_per_settlement is not None
    return {
        "schemaVersion": "s01_formal_funding_stress_v1",
        "historicalFundingMissingValue": None,
        "rawFundingMissingFilledWithZero": False,
        "fundingEvidenceStatus": "partial_or_proxy",
        "proxyMethod": (
            "adverse_same_exchange_quantile_per_observed_8h_settlement"
            if available
            else "unavailable_no_registered_same_exchange_history"
        ),
        "adverseRatePerSettlement": adverse_rate_per_settlement,
        "gateEvaluable": available,
        "events": output,
    }


def build_same_event_fixed_hold_benchmark(
    events: Sequence[Mapping[str, Any]],
    frames: Mapping[str, pd.DataFrame],
    *,
    hold_bars: int = 12,
) -> dict[str, Any]:
    """Apply a preregistered same-event fixed-hold benchmark."""

    rows: list[dict[str, Any]] = []
    for event in events:
        frame = frames[str(event["symbol"])]
        entry_index = int(event["entryIndex"])
        exit_index = min(entry_index + int(hold_bars), len(frame) - 1)
        entry_price = float(event["entryPrice"])
        exit_price = float(frame.iloc[exit_index]["open"])
        risk_distance = float(event["riskDistance"])
        direction = 1.0 if str(event.get("side") or event.get("direction")) == "long" else -1.0
        gross_r = direction * (exit_price - entry_price) / risk_distance
        cost_r = _nonfunding_cost_r(event)
        rows.append(
            {
                "signalId": canonical_event_id(event),
                "candidateId": event.get("candidateId"),
                "symbol": event["symbol"],
                "foldId": event.get("foldId"),
                "entryTimestamp": event["entryTimestamp"],
                "benchmarkExitIndex": exit_index,
                "benchmarkExitTimestamp": pd.Timestamp(frame.iloc[exit_index]["date"]).isoformat(),
                "benchmarkExitPrice": exit_price,
                "benchmarkGrossR": gross_r,
                "benchmarkCostR": cost_r,
                "benchmarkNetR": gross_r - cost_r,
                "candidateNetR": float(event.get("realizedNetR") or 0.0),
                "incrementalNetR": float(event.get("realizedNetR") or 0.0) - (gross_r - cost_r),
            }
        )
    by_fold: list[dict[str, Any]] = []
    fold_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        fold_events[str(row.get("foldId") or "unassigned")].append(row)
    for fold_id, values in sorted(fold_events.items()):
        by_fold.append(
            {
                "foldId": fold_id,
                "eventCount": len(values),
                "candidateNetR": sum(float(row["candidateNetR"]) for row in values),
                "benchmarkNetR": sum(float(row["benchmarkNetR"]) for row in values),
                "incrementalNetR": sum(float(row["incrementalNetR"]) for row in values),
            }
        )
    return {
        "schemaVersion": "formal_same_event_fixed_hold_benchmark_v1",
        "benchmarkName": "same_event_fixed_12_bar_exit",
        "holdBars": hold_bars,
        "events": rows,
        "folds": by_fold,
        "totalIncrementalNetR": sum(float(row["incrementalNetR"]) for row in rows),
        "positiveIncrementFoldCount": sum(float(row["incrementalNetR"]) > 0 for row in by_fold),
    }


def build_s01_benchmark(
    events: Sequence[Mapping[str, Any]],
    frames: Mapping[str, pd.DataFrame],
    *,
    hold_bars: int = 12,
) -> dict[str, Any]:
    """Preserve the frozen S01 benchmark contract through the shared builder."""

    result = build_same_event_fixed_hold_benchmark(
        events,
        frames,
        hold_bars=hold_bars,
    )
    return {
        **result,
        "schemaVersion": "s01_formal_same_event_benchmark_v1",
    }


def build_utc_daily_returns(
    accepted_events: Sequence[Mapping[str, Any]],
    *,
    start: str,
    cutoff_exclusive: str,
    initial_equity: float | None = None,
) -> pd.DataFrame:
    """Build a zero-filled UTC daily panel from realized portfolio exits."""

    start_day = pd.Timestamp(start).floor("D")
    cutoff_day = pd.Timestamp(cutoff_exclusive).floor("D")
    dates = pd.date_range(start_day, cutoff_day, freq="D", inclusive="left")
    pnl_by_day: dict[pd.Timestamp, float] = defaultdict(float)
    for event in accepted_events:
        exit_day = pd.Timestamp(str(event["exitTimestamp"])).floor("D")
        pnl_by_day[exit_day] += float(event.get("netPnl") or 0.0)
    if initial_equity is None:
        initial_equity = min(
            (float(event.get("equityAtEntry") or 0.0) for event in accepted_events),
            default=10_000.0,
        )
    equity = float(initial_equity)
    rows = []
    for day in dates:
        pnl = float(pnl_by_day.get(day, 0.0))
        return_value = pnl / equity if equity else 0.0
        equity += pnl
        rows.append(
            {
                "date": day,
                "netPnl": pnl,
                "netReturn": return_value,
                "endEquity": equity,
            }
        )
    return pd.DataFrame(rows)
