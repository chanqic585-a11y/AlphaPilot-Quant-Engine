"""Chronological shared-capital replay for frozen formal event candidates."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Mapping, Sequence


def _timestamp(value: object) -> datetime:
    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _ranking_key(event: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        _timestamp(event["entryTimestamp"]),
        float(event.get("residualZ") or 0.0),
        -float(event.get("recoveryConfirmation") or 0.0),
        -float(event.get("liquidityScore") or 0.0),
        str(event.get("symbol") or ""),
        str(event.get("signalId") or ""),
    )


def replay_shared_capital(
    events: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply the frozen risk policy to one chronological pool of signals.

    PnL is realized before each later entry, so the next trade risks the frozen
    percentage of then-realized equity. Open trades compete for the same risk
    budget; no candidate or symbol receives a private capital account.
    """

    initial_equity = float(policy["initial_capital"])
    equity = initial_equity
    active: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = [
        {"timestamp": None, "equity": initial_equity, "event": "initial"}
    ]

    def close_through(cutoff: datetime | None) -> None:
        nonlocal equity, active
        closing = sorted(
            (
                row
                for row in active
                if cutoff is None or _timestamp(row["exitTimestamp"]) <= cutoff
            ),
            key=lambda row: (
                _timestamp(row["exitTimestamp"]),
                str(row["symbol"]),
                str(row.get("signalId") or ""),
            ),
        )
        closed_ids = {id(row) for row in closing}
        for row in closing:
            equity += float(row["netPnl"])
            row["equityAfterExit"] = equity
            equity_curve.append(
                {
                    "timestamp": row["exitTimestamp"],
                    "equity": equity,
                    "event": "exit",
                    "signalId": row.get("signalId"),
                    "symbol": row["symbol"],
                }
            )
        active = [row for row in active if id(row) not in closed_ids]

    for raw in sorted((dict(row) for row in events), key=_ranking_key):
        entry_time = _timestamp(raw["entryTimestamp"])
        close_through(entry_time)
        direction = str(raw.get("direction") or raw.get("side") or "unknown")
        symbol = str(raw.get("symbol") or "unknown")
        cluster = str(raw.get("correlationCluster") or "unclustered")
        beta = abs(float(raw.get("portfolioBeta") or 0.0))
        risk_fraction = float(policy["risk_per_trade"])
        risk_amount = equity * risk_fraction
        active_risk = sum(float(row["riskAmount"]) for row in active)
        direction_risk = sum(
            float(row["riskAmount"])
            for row in active
            if row["direction"] == direction
        )
        cluster_risk = sum(
            float(row["riskAmount"])
            for row in active
            if row["correlationCluster"] == cluster
        )
        symbol_risk = sum(
            float(row["riskAmount"])
            for row in active
            if row["symbol"] == symbol
        )
        active_beta = sum(float(row["portfolioBeta"]) for row in active)
        reason: str | None = None
        if raw.get("capacityPassed") is not True:
            reason = "capacity_rejected"
        elif any(row["symbol"] == symbol for row in active):
            reason = "duplicate_symbol_while_open"
        elif len(active) >= int(policy["maximum_concurrent_positions"]):
            reason = "concurrent_position_limit"
        elif active_risk + risk_amount > equity * float(policy["maximum_open_risk"]) + 1e-9:
            reason = "open_risk_limit"
        elif direction_risk + risk_amount > equity * float(policy["maximum_same_direction_risk"]) + 1e-9:
            reason = "same_direction_risk_limit"
        elif cluster_risk + risk_amount > equity * float(policy["maximum_correlation_cluster_risk"]) + 1e-9:
            reason = "correlation_cluster_risk_limit"
        elif symbol_risk + risk_amount > equity * float(policy["maximum_single_symbol_risk"]) + 1e-9:
            reason = "single_symbol_risk_limit"
        elif active_beta + beta > float(policy["maximum_portfolio_beta"]) + 1e-9:
            reason = "portfolio_beta_limit"
        if reason:
            rejected.append({**raw, "reason": reason})
            continue

        net_r = float(raw.get("realizedNetR") or 0.0)
        gross_r = float(raw.get("realizedGrossR") or net_r)
        row = {
            **raw,
            "direction": direction,
            "correlationCluster": cluster,
            "portfolioBeta": beta,
            "riskFraction": risk_fraction,
            "riskAmount": risk_amount,
            "grossPnl": gross_r * risk_amount,
            "netPnl": net_r * risk_amount,
            "equityAtEntry": equity,
        }
        accepted.append(row)
        active.append(row)

    close_through(None)
    reason_counts = Counter(str(row["reason"]) for row in rejected)
    return {
        "schemaVersion": "s01_formal_shared_capital_v1",
        "initialEquity": initial_equity,
        "finalEquity": equity,
        "accepted": accepted,
        "rejected": rejected,
        "equityCurve": equity_curve,
        "audit": {
            "inputEventCount": len(events),
            "acceptedEventCount": len(accepted),
            "rejectedEventCount": len(rejected),
            "rejectionReasons": dict(sorted(reason_counts.items())),
            "lookaheadReadCount": 0,
            "sharedCapitalAccountCount": 1,
            "riskSizing": "current_realized_equity_times_frozen_risk_fraction",
            "policy": dict(policy),
        },
    }


def replay_locked_selection(
    events: Sequence[Mapping[str, Any]], policy: Mapping[str, Any]
) -> dict[str, Any]:
    """Reprice a base-selected event set without rerunning signal selection.

    Cost and funding stress scenarios must keep the base scenario's accepted
    event identities fixed.  This replay therefore compounds the same frozen
    trades while changing only their preregistered scenario PnL.
    """

    initial_equity = float(policy["initial_capital"])
    equity = initial_equity
    active: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = [
        {"timestamp": None, "equity": initial_equity, "event": "initial"}
    ]

    def close_through(cutoff: datetime | None) -> None:
        nonlocal equity, active
        closing = sorted(
            (
                row
                for row in active
                if cutoff is None or _timestamp(row["exitTimestamp"]) <= cutoff
            ),
            key=lambda row: (
                _timestamp(row["exitTimestamp"]),
                str(row["symbol"]),
                str(row.get("signalId") or ""),
            ),
        )
        closed_ids = {id(row) for row in closing}
        for row in closing:
            equity += float(row["netPnl"])
            row["equityAfterExit"] = equity
            equity_curve.append(
                {
                    "timestamp": row["exitTimestamp"],
                    "equity": equity,
                    "event": "exit",
                    "signalId": row.get("signalId"),
                    "symbol": row["symbol"],
                }
            )
        active = [row for row in active if id(row) not in closed_ids]

    for raw in sorted((dict(row) for row in events), key=_ranking_key):
        close_through(_timestamp(raw["entryTimestamp"]))
        risk_fraction = float(policy["risk_per_trade"])
        risk_amount = equity * risk_fraction
        net_r = float(raw.get("realizedNetR") or 0.0)
        gross_r = float(raw.get("realizedGrossR") or net_r)
        row = {
            **raw,
            "riskFraction": risk_fraction,
            "riskAmount": risk_amount,
            "grossPnl": gross_r * risk_amount,
            "netPnl": net_r * risk_amount,
            "equityAtEntry": equity,
        }
        accepted.append(row)
        active.append(row)

    close_through(None)
    return {
        "schemaVersion": "s01_formal_locked_selection_replay_v1",
        "initialEquity": initial_equity,
        "finalEquity": equity,
        "accepted": accepted,
        "rejected": [],
        "equityCurve": equity_curve,
        "audit": {
            "inputEventCount": len(events),
            "acceptedEventCount": len(accepted),
            "rejectedEventCount": 0,
            "lookaheadReadCount": 0,
            "sharedCapitalAccountCount": 1,
            "selectionPolicy": "frozen_base_accepted_event_identities",
            "riskSizing": "current_realized_equity_times_frozen_risk_fraction",
            "policy": dict(policy),
        },
    }


def _maximum_drawdown_percent(equities: Sequence[float]) -> float:
    peak = float(equities[0]) if equities else 0.0
    maximum = 0.0
    for value in equities:
        peak = max(peak, float(value))
        if peak > 0:
            maximum = max(maximum, (peak - float(value)) / peak * 100.0)
    return maximum


def summarize_portfolio(result: Mapping[str, Any]) -> dict[str, Any]:
    accepted = [dict(row) for row in result.get("accepted", [])]
    pnls = [float(row["netPnl"]) for row in accepted]
    net_rs = [float(row.get("realizedNetR") or 0.0) for row in accepted]
    positive_pnl = sum(value for value in pnls if value > 0)
    negative_pnl = abs(sum(value for value in pnls if value < 0))
    by_symbol: dict[str, float] = defaultdict(float)
    by_month: dict[str, float] = defaultdict(float)
    for row in accepted:
        pnl = max(0.0, float(row["netPnl"]))
        by_symbol[str(row["symbol"])] += pnl
        month = _timestamp(row["exitTimestamp"]).strftime("%Y-%m")
        by_month[month] += pnl
    initial = float(result.get("initialEquity") or 0.0)
    final = float(result.get("finalEquity") or initial)
    equities = [float(row["equity"]) for row in result.get("equityCurve", [])]
    denominator = positive_pnl if positive_pnl > 0 else 1.0
    return {
        "schemaVersion": "s01_formal_portfolio_metrics_v1",
        "metricType": "event_shared_capital",
        "tradeCount": len(accepted),
        "winCount": sum(value > 0 for value in pnls),
        "lossCount": sum(value < 0 for value in pnls),
        "profitFactor": positive_pnl / negative_pnl if negative_pnl > 0 else None,
        "profitFactorStatus": "defined" if negative_pnl > 0 else "undefined_no_losses",
        "averageNetR": sum(net_rs) / len(net_rs) if net_rs else 0.0,
        "totalNetR": sum(net_rs),
        "netPnl": final - initial,
        "netReturnPercent": ((final / initial) - 1.0) * 100.0 if initial else 0.0,
        "maximumDrawdownPercent": _maximum_drawdown_percent(equities),
        "maximumSingleSymbolPositiveContribution": (
            max(by_symbol.values(), default=0.0) / denominator
        ),
        "maximumSingleMonthPositiveContribution": (
            max(by_month.values(), default=0.0) / denominator
        ),
        "positiveContributionBySymbol": dict(sorted(by_symbol.items())),
        "positiveContributionByMonth": dict(sorted(by_month.items())),
    }
