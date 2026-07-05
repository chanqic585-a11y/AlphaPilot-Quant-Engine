"""Local paper sandbox ledger simulation.

The ledger in this module is a local research accounting model. It consumes
historical signal rows that already include entry/exit timestamps and simulated
net returns. It does not call exchange APIs, read real balances, create orders,
or auto trade.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class LocalPaperSandboxConfig:
    account_id: str = "default_local_paper_sandbox"
    initial_equity: float = 10_000.0
    risk_per_signal_pct: float = 1.0
    max_concurrent_positions: int = 3
    max_notional_per_signal_pct: float = 35.0
    stop_loss_pct: float = 0.045
    source: str = "local_paper_sandbox_v13_5_3"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _to_timestamp(value: Any) -> pd.Timestamp | None:
    if value is None:
        return None
    timestamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(timestamp):
        return None
    return timestamp


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _max_drawdown_pct(equity_values: list[float]) -> float:
    if not equity_values:
        return 0.0
    peak = equity_values[0]
    max_drawdown = 0.0
    for value in equity_values:
        peak = max(peak, value)
        if peak <= 0:
            continue
        max_drawdown = max(max_drawdown, (peak - value) / peak * 100)
    return round(max_drawdown, 6)


def _metrics_from_fills(fills: list[dict[str, Any]], initial_equity: float, final_equity: float) -> dict[str, Any]:
    closed = [fill for fill in fills if fill.get("status") == "closed"]
    wins = [fill for fill in closed if (fill.get("pnl") or 0) > 0]
    losses = [fill for fill in closed if (fill.get("pnl") or 0) < 0]
    average_win = sum(fill["pnl"] for fill in wins) / len(wins) if wins else None
    average_loss = sum(fill["pnl"] for fill in losses) / len(losses) if losses else None
    reward_risk = (average_win / abs(average_loss)) if average_win is not None and average_loss and average_loss < 0 else None
    gross_profit = sum(fill["pnl"] for fill in wins)
    gross_loss = abs(sum(fill["pnl"] for fill in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
    return {
        "tradeCount": len(closed),
        "winCount": len(wins),
        "lossCount": len(losses),
        "winRatePct": _round(len(wins) / len(closed) * 100, 4) if closed else None,
        "averageWin": _round(average_win),
        "averageLoss": _round(average_loss),
        "rewardRiskRatio": _round(reward_risk, 4),
        "profitFactor": _round(profit_factor, 4),
        "initialEquity": _round(initial_equity),
        "finalEquity": _round(final_equity),
        "totalReturnPct": _round(((final_equity / initial_equity) - 1) * 100, 4) if initial_equity > 0 else None,
    }


def simulate_local_paper_ledger(
    signal_rows: list[dict[str, Any]],
    approved_candidate_ids: list[str],
    config: LocalPaperSandboxConfig | None = None,
) -> dict[str, Any]:
    """Replay approved signal rows into a local paper ledger.

    Position sizing uses fixed risk per signal:

    ``risk_amount = equity * risk_per_signal_pct / 100``
    ``notional = min(risk_amount / stop_loss_pct, equity * max_notional_per_signal_pct / 100)``

    PnL is based on the historical signal row's `netReturnPct`. This is a local
    research replay, not a live fill simulation.
    """

    cfg = config or LocalPaperSandboxConfig()
    approved = set(approved_candidate_ids)
    equity = float(cfg.initial_equity)
    cash_balance = float(cfg.initial_equity)
    used_notional = 0.0
    open_positions: list[dict[str, Any]] = []
    fills: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = [
        {
            "timestamp": None,
            "equity": _round(equity),
            "cashBalance": _round(cash_balance),
            "openPositionCount": 0,
            "event": "initial",
        }
    ]

    prepared_rows = []
    for index, row in enumerate(signal_rows):
        candidate_id = str(row.get("candidateId") or "")
        entry_time = _to_timestamp(row.get("entryDate"))
        exit_time = _to_timestamp(row.get("exitDate"))
        if candidate_id not in approved:
            skipped.append(
                {
                    "signalIndex": index,
                    "candidateId": candidate_id,
                    "reason": "candidate_not_approved_for_local_paper",
                }
            )
            continue
        if entry_time is None or exit_time is None:
            skipped.append(
                {
                    "signalIndex": index,
                    "candidateId": candidate_id,
                    "reason": "invalid_entry_or_exit_time",
                }
            )
            continue
        prepared_rows.append((entry_time, exit_time, index, row))
    prepared_rows.sort(key=lambda item: (item[0], item[1], item[2]))

    for entry_time, exit_time, index, row in prepared_rows:
        still_open = []
        for position in sorted(open_positions, key=lambda item: item["exitTime"]):
            if position["exitTime"] <= entry_time:
                equity += position["pnl"]
                cash_balance += position["pnl"]
                used_notional -= position["notionalValue"]
                closed_fill = {
                    **position["fill"],
                    "status": "closed",
                    "closedAt": position["exitTime"].isoformat(),
                    "equityAfterClose": _round(equity),
                    "cashBalanceAfterClose": _round(cash_balance),
                }
                fills.append(closed_fill)
                equity_curve.append(
                    {
                        "timestamp": position["exitTime"].isoformat(),
                        "equity": _round(equity),
                        "cashBalance": _round(cash_balance),
                        "openPositionCount": max(0, len(open_positions) - 1),
                        "event": "close",
                        "candidateId": position["candidateId"],
                        "pair": position["pair"],
                    }
                )
            else:
                still_open.append(position)
        open_positions = still_open

        if len(open_positions) >= cfg.max_concurrent_positions:
            skipped.append(
                {
                    "signalIndex": index,
                    "candidateId": row.get("candidateId"),
                    "pair": row.get("pair"),
                    "entryDate": entry_time.isoformat(),
                    "reason": "max_concurrent_positions_reached",
                }
            )
            continue

        entry_price = float(row.get("entryPrice") or 0)
        net_return_pct = float(row.get("netReturnPct") or 0)
        if entry_price <= 0:
            skipped.append(
                {
                    "signalIndex": index,
                    "candidateId": row.get("candidateId"),
                    "pair": row.get("pair"),
                    "entryDate": entry_time.isoformat(),
                    "reason": "invalid_entry_price",
                }
            )
            continue

        risk_amount = equity * cfg.risk_per_signal_pct / 100
        notional_from_risk = risk_amount / cfg.stop_loss_pct if cfg.stop_loss_pct > 0 else 0
        max_notional = equity * cfg.max_notional_per_signal_pct / 100
        notional_value = min(notional_from_risk, max_notional)
        if notional_value <= 0:
            skipped.append(
                {
                    "signalIndex": index,
                    "candidateId": row.get("candidateId"),
                    "pair": row.get("pair"),
                    "entryDate": entry_time.isoformat(),
                    "reason": "invalid_notional",
                }
            )
            continue
        quantity = notional_value / entry_price
        pnl = notional_value * net_return_pct / 100
        position_id = f"paper-{len(fills) + len(open_positions) + 1:05d}"
        fill = {
            "positionId": position_id,
            "signalIndex": index,
            "candidateId": row.get("candidateId"),
            "pair": row.get("pair"),
            "timeframe": row.get("timeframe"),
            "setupName": row.get("setupName"),
            "direction": row.get("direction"),
            "entryDate": entry_time.isoformat(),
            "exitDate": exit_time.isoformat(),
            "entryPrice": _round(entry_price, 8),
            "exitPrice": _round(float(row.get("exitPrice") or 0), 8),
            "quantity": _round(quantity, 8),
            "riskAmount": _round(risk_amount),
            "notionalValue": _round(notional_value),
            "netReturnPct": _round(net_return_pct),
            "pnl": _round(pnl),
            "rMultiple": _round(float(row.get("rMultiple") or 0)),
            "exitReason": row.get("exitReason"),
            "status": "open",
            "source": cfg.source,
        }
        open_positions.append(
            {
                "positionId": position_id,
                "candidateId": row.get("candidateId"),
                "pair": row.get("pair"),
                "exitTime": exit_time,
                "notionalValue": notional_value,
                "pnl": pnl,
                "fill": fill,
            }
        )
        used_notional += notional_value
        equity_curve.append(
            {
                "timestamp": entry_time.isoformat(),
                "equity": _round(equity),
                "cashBalance": _round(cash_balance),
                "usedNotional": _round(used_notional),
                "openPositionCount": len(open_positions),
                "event": "open",
                "candidateId": row.get("candidateId"),
                "pair": row.get("pair"),
            }
        )

    for position in sorted(open_positions, key=lambda item: item["exitTime"]):
        equity += position["pnl"]
        cash_balance += position["pnl"]
        used_notional -= position["notionalValue"]
        fills.append(
            {
                **position["fill"],
                "status": "closed",
                "closedAt": position["exitTime"].isoformat(),
                "equityAfterClose": _round(equity),
                "cashBalanceAfterClose": _round(cash_balance),
            }
        )
        equity_curve.append(
            {
                "timestamp": position["exitTime"].isoformat(),
                "equity": _round(equity),
                "cashBalance": _round(cash_balance),
                "openPositionCount": 0,
                "event": "close",
                "candidateId": position["candidateId"],
                "pair": position["pair"],
            }
        )

    equity_values = [float(item["equity"]) for item in equity_curve if item.get("equity") is not None]
    metrics = _metrics_from_fills(fills, cfg.initial_equity, equity)
    metrics["maxDrawdownPct"] = _max_drawdown_pct(equity_values)
    metrics["skippedSignalCount"] = len(skipped)
    metrics["filledSignalCount"] = len(fills)
    metrics["maxConcurrentPositions"] = cfg.max_concurrent_positions

    return {
        "config": cfg.to_dict(),
        "metrics": metrics,
        "fills": fills,
        "skippedSignals": skipped,
        "equityCurve": equity_curve,
        "generatedAt": utc_now(),
        "safetyBoundary": {
            "localSimulationOnly": True,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "readsRealAccount": False,
            "readsRealPositions": False,
            "createsOrders": False,
            "autoTrading": False,
        },
    }
