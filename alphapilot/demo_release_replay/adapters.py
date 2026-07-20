"""Adapters around the historical 1d and 1h research engines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np
import pandas as pd

from alphapilot.low_frequency.strategy_candidate_factory import (
    _candidate_specs,
    _simulate_candidate,
)
from alphapilot.short_cycle.parameter_search import (
    add_indicators,
    build_signal,
    merge_btc_context,
    simulate_trades,
)


REPLAY_STATUS = "research_replay_only"


@dataclass(frozen=True)
class ReplayResult:
    candidate_id: str
    family: str
    timeframe: str
    direction: str
    selected_pairs: tuple[str, ...]
    trades: tuple[dict[str, Any], ...]
    metrics: Mapping[str, Any]
    split_metrics: Mapping[str, Mapping[str, Any]]
    status: str = REPLAY_STATUS

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidateId": self.candidate_id,
            "direction": self.direction,
            "family": self.family,
            "metrics": dict(self.metrics),
            "selectedPairs": list(self.selected_pairs),
            "splitMetrics": {key: dict(value) for key, value in self.split_metrics.items()},
            "status": self.status,
            "timeframe": self.timeframe,
            "tradeCount": len(self.trades),
        }


def canonicalize_trades(
    rows: list[dict[str, Any]],
    *,
    candidate_id: str,
    family: str,
    timeframe: str,
    direction: str,
    source_exchange: str,
) -> tuple[dict[str, Any], ...]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        entry_date = row.get("entryDate", row.get("entryTimestamp"))
        exit_date = row.get("exitDate", row.get("exitTimestamp"))
        if not entry_date or not exit_date:
            raise ValueError("trade_missing_entry_or_exit_date")
        normalized.append(
            {
                "candidateId": candidate_id,
                "direction": direction,
                "entryDate": str(entry_date),
                "entryPrice": row.get("entryPrice"),
                "exitDate": str(exit_date),
                "exitPrice": row.get("exitPrice"),
                "exitReason": row.get("exitReason"),
                "family": family,
                "feeR": row.get("feeR"),
                "grossR": row.get("grossR"),
                "holdCandles": row.get("holdCandles", row.get("holdBars")),
                "netR": row.get("netR"),
                "pair": row.get("pair"),
                "sourceExchange": source_exchange,
                "stopPrice": row.get("stopPrice"),
                "targetPrice": row.get("targetPrice"),
                "timeframe": timeframe,
            }
        )
    return tuple(sorted(normalized, key=lambda row: (row["entryDate"], str(row["pair"]))))


def canonical_metrics(trades: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "expectancyR": None,
            "lossCount": 0,
            "maxDrawdownR": 0.0,
            "pairCount": 0,
            "profitFactor": None,
            "stopHitRatePct": None,
            "targetHitRatePct": None,
            "totalR": 0.0,
            "tradeCount": 0,
            "winCount": 0,
            "winRatePct": None,
        }
    values = np.array([float(row["netR"]) for row in trades], dtype=float)
    wins = values[values > 0]
    losses = values[values < 0]
    cumulative = np.cumsum(values)
    peaks = np.maximum.accumulate(np.insert(cumulative, 0, 0.0))[1:]
    drawdown = peaks - cumulative
    profit_factor = float(wins.sum() / abs(losses.sum())) if losses.size else None
    target_hits = sum("target" in str(row.get("exitReason", "")) for row in trades)
    stop_hits = sum("stop" in str(row.get("exitReason", "")) for row in trades)
    count = len(trades)
    return {
        "expectancyR": round(float(values.mean()), 6),
        "lossCount": int((values < 0).sum()),
        "maxDrawdownR": round(float(drawdown.max() if drawdown.size else 0.0), 4),
        "pairCount": len({str(row.get("pair")) for row in trades}),
        "profitFactor": round(profit_factor, 4) if profit_factor is not None else None,
        "stopHitRatePct": round(stop_hits / count * 100, 4),
        "targetHitRatePct": round(target_hits / count * 100, 4),
        "totalR": round(float(values.sum()), 4),
        "tradeCount": count,
        "winCount": int((values > 0).sum()),
        "winRatePct": round(float((values > 0).mean() * 100), 4),
    }


def canonical_split_metrics(
    trades: tuple[dict[str, Any], ...],
    *,
    mode: str,
) -> dict[str, dict[str, Any]]:
    if mode not in {"fixed_calendar", "relative_50_25_25"}:
        raise ValueError(f"unsupported_split_mode:{mode}")
    if not trades:
        keys = ("train", "validation", "test")
        return {key: canonical_metrics([]) for key in keys}

    dates = pd.to_datetime([row["entryDate"] for row in trades], utc=True)
    buckets: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "test": []}
    if mode == "fixed_calendar":
        train_end = pd.Timestamp("2023-01-01", tz="UTC")
        validation_end = pd.Timestamp("2025-01-01", tz="UTC")
    else:
        start, end = dates.min(), dates.max()
        span = end - start
        train_end = start + span * 0.50
        validation_end = start + span * 0.75
    for row, date in zip(trades, dates, strict=True):
        if date < train_end:
            buckets["train"].append(row)
        elif date < validation_end:
            buckets["validation"].append(row)
        else:
            buckets["test"].append(row)
    return {key: canonical_metrics(value) for key, value in buckets.items()}


def replay_short_cycle_candidate(
    candidate: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame],
    *,
    fee_rate: float = 0.0005,
    slippage_rate: float = 0.0005,
) -> ReplayResult:
    candidate_id = str(candidate["candidateId"])
    family = str(candidate["family"])
    direction = str(candidate["direction"])
    timeframe = str(candidate["timeframe"])
    params = dict(candidate["params"])
    selected_pairs = tuple(sorted(str(pair) for pair in candidate["assetFilter"]["selectedPairs"]))
    missing = [pair for pair in selected_pairs if pair not in frames]
    if missing:
        raise ValueError(f"selected_pairs_missing:{','.join(missing)}")

    btc_raw = frames.get("BTC/USDT:USDT")
    btc = None
    if btc_raw is not None:
        btc = btc_raw.copy() if "ema20" in btc_raw.columns else add_indicators(btc_raw)

    raw_trades: list[dict[str, Any]] = []
    for pair in selected_pairs:
        frame = frames[pair].copy()
        if "atr14" not in frame.columns or "ema20" not in frame.columns:
            frame = add_indicators(frame)
        if "btc_ret_3" not in frame.columns:
            frame = merge_btc_context(frame, btc)
        signal, actual_direction = build_signal(frame, family, params)
        if actual_direction != direction:
            raise ValueError(f"direction_mismatch:{actual_direction}!={direction}")
        raw_trades.extend(
            simulate_trades(
                frame,
                signal,
                direction,
                stop_atr=float(params["stop_atr"]),
                max_hold=int(params["max_hold"]),
                target_r=float(candidate.get("targetR", 2.0)),
                fee_rate=fee_rate,
                slippage_rate=slippage_rate,
            )
        )

    trades = canonicalize_trades(
        raw_trades,
        candidate_id=candidate_id,
        family=family,
        timeframe=timeframe,
        direction=direction,
        source_exchange="binance_vision_public",
    )
    return ReplayResult(
        candidate_id=candidate_id,
        family=family,
        timeframe=timeframe,
        direction=direction,
        selected_pairs=selected_pairs,
        trades=trades,
        metrics=canonical_metrics(trades),
        split_metrics=canonical_split_metrics(trades, mode="relative_50_25_25"),
    )


def _low_frequency_source_id(candidate_id: str) -> str:
    prefix = "v13_7_20_"
    return candidate_id[len(prefix) :] if candidate_id.startswith(prefix) else candidate_id


def replay_low_frequency_candidate(
    candidate_id: str,
    prepared_frames: Mapping[str, pd.DataFrame],
) -> ReplayResult:
    source_id = _low_frequency_source_id(candidate_id)
    matches = [spec for spec in _candidate_specs() if spec.candidate_id == source_id]
    if len(matches) != 1:
        raise ValueError(f"low_frequency_spec_not_found:{candidate_id}")
    spec = matches[0]
    raw_trades = _simulate_candidate(spec, dict(prepared_frames))
    trades = canonicalize_trades(
        raw_trades,
        candidate_id=candidate_id,
        family=spec.family,
        timeframe=spec.timeframe,
        direction="long",
        source_exchange="okx_public",
    )
    return ReplayResult(
        candidate_id=candidate_id,
        family=spec.family,
        timeframe=spec.timeframe,
        direction="long",
        selected_pairs=tuple(sorted(prepared_frames)),
        trades=trades,
        metrics=canonical_metrics(trades),
        split_metrics=canonical_split_metrics(trades, mode="fixed_calendar"),
    )
