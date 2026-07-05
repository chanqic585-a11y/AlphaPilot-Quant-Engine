"""Triple-barrier labeling and event simulation for V13.5 research."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BarrierConfig:
    stop_loss_pct: float = 0.025
    reward_r_multiple: float = 2.0
    horizon_bars: int = 18
    fee_rate_roundtrip: float = 0.001
    slippage_rate_roundtrip: float = 0.001


def _candidate_setups(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    funding_available = out["funding_rate"].notna()
    funding_low = out["funding_z_60"] <= -0.8
    funding_high = out["funding_z_60"] >= 0.8
    basis_low = out["mark_basis_pct"] <= -0.0008
    basis_high = out["mark_basis_pct"] >= 0.0008
    volume_active = out["volume_ratio"] >= 1.05
    not_crashing = ~out["btc_crash_block"].fillna(False)

    out["long_reversal_candidate"] = (
        (out["return_3"] <= -0.025)
        & (out["rsi14"] <= 45)
        & (out["support_distance_pct"] <= 0.06)
        & volume_active
        & not_crashing
        & ((funding_available & funding_low) | basis_low | (out["bollinger_z"] <= -1.0))
    )
    out["short_reversal_candidate"] = (
        (out["return_3"] >= 0.025)
        & (out["rsi14"] >= 55)
        & (out["resistance_distance_pct"] <= 0.06)
        & volume_active
        & ((funding_available & funding_high) | basis_high | (out["bollinger_z"] >= 1.0))
    )
    out["long_continuation_candidate"] = (
        (out["ema200_gap"] > 0)
        & (out["return_3"].between(-0.03, 0.01))
        & (out["relative_return_6"] > 0)
        & (out["rsi14"].between(42, 62))
        & (out["volume_ratio"] >= 0.8)
        & not_crashing
    )
    return out


def _simulate_one(
    pair_frame: pd.DataFrame,
    row_position: int,
    direction: str,
    config: BarrierConfig,
) -> dict[str, object] | None:
    entry_position = row_position + 1
    if entry_position >= len(pair_frame):
        return None
    entry_row = pair_frame.iloc[entry_position]
    entry_price = float(entry_row["open"])
    if not np.isfinite(entry_price) or entry_price <= 0:
        return None

    if direction == "long":
        stop_price = entry_price * (1 - config.stop_loss_pct)
        target_price = entry_price * (1 + config.stop_loss_pct * config.reward_r_multiple)
    else:
        stop_price = entry_price * (1 + config.stop_loss_pct)
        target_price = entry_price * (1 - config.stop_loss_pct * config.reward_r_multiple)

    exit_price = float(pair_frame.iloc[min(entry_position + config.horizon_bars, len(pair_frame) - 1)]["close"])
    exit_date = pair_frame.iloc[min(entry_position + config.horizon_bars, len(pair_frame) - 1)]["date"]
    exit_reason = "time_exit"
    holding_bars = min(config.horizon_bars, len(pair_frame) - entry_position - 1)

    for offset in range(config.horizon_bars):
        current_position = entry_position + offset
        if current_position >= len(pair_frame):
            break
        candle = pair_frame.iloc[current_position]
        high = float(candle["high"])
        low = float(candle["low"])
        if direction == "long":
            stop_hit = low <= stop_price
            target_hit = high >= target_price
        else:
            stop_hit = high >= stop_price
            target_hit = low <= target_price
        if stop_hit and target_hit:
            # Conservative same-candle ordering.
            exit_price = stop_price
            exit_reason = "stop_loss_same_candle"
        elif stop_hit:
            exit_price = stop_price
            exit_reason = "stop_loss"
        elif target_hit:
            exit_price = target_price
            exit_reason = "take_profit_2r"
        else:
            continue
        exit_date = candle["date"]
        holding_bars = offset + 1
        break

    gross_return = (exit_price / entry_price) - 1 if direction == "long" else (entry_price / exit_price) - 1
    cost = config.fee_rate_roundtrip + config.slippage_rate_roundtrip
    net_return = gross_return - cost
    r_multiple = net_return / config.stop_loss_pct
    return {
        "entryDate": entry_row["date"],
        "exitDate": exit_date,
        "entryPrice": round(entry_price, 8),
        "exitPrice": round(float(exit_price), 8),
        "direction": direction,
        "exitReason": exit_reason,
        "holdingBars": int(holding_bars),
        "grossReturnPct": round(gross_return * 100, 6),
        "netReturnPct": round(net_return * 100, 6),
        "rMultiple": round(r_multiple, 6),
        "isWin": bool(net_return > 0),
        "targetR": config.reward_r_multiple,
        "stopLossPct": config.stop_loss_pct,
    }


def build_labeled_events(
    panel: pd.DataFrame,
    config: BarrierConfig,
    setups: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Create candidate-event rows and attach triple-barrier outcomes."""

    setup_names = list(
        setups
        or [
            "long_reversal_candidate",
            "short_reversal_candidate",
            "long_continuation_candidate",
        ]
    )
    prepared = _candidate_setups(panel)
    events: list[dict[str, object]] = []
    feature_columns = [
        "pair",
        "date",
        "timeframe",
        "close",
        "return_3",
        "return_6",
        "return_12",
        "ema200_gap",
        "rsi14",
        "atr_pct",
        "range_pct",
        "volatility_12",
        "volume_ratio",
        "bollinger_z",
        "support_distance_pct",
        "resistance_distance_pct",
        "mark_basis_pct",
        "funding_rate",
        "funding_z_60",
        "btc_return_3",
        "btc_return_6",
        "btc_return_12",
        "btc_ema200_gap",
        "btc_volatility_12",
        "relative_return_6",
        "btc_regime",
    ]

    for pair, pair_frame in prepared.groupby("pair", sort=False):
        pair_frame = pair_frame.sort_values("date").reset_index(drop=True)
        for position, row in pair_frame.iterrows():
            active_setups = [name for name in setup_names if bool(row.get(name, False))]
            for setup_name in active_setups:
                direction = "short" if setup_name.startswith("short") else "long"
                outcome = _simulate_one(pair_frame, position, direction, config)
                if outcome is None:
                    continue
                event = {column: row.get(column) for column in feature_columns}
                event.update(outcome)
                event["setupName"] = setup_name
                event["signalDate"] = row["date"]
                event["pair"] = pair
                events.append(event)

    if not events:
        return pd.DataFrame()
    output = pd.DataFrame(events)
    output["signalDate"] = pd.to_datetime(output["signalDate"], utc=True)
    output["entryDate"] = pd.to_datetime(output["entryDate"], utc=True)
    output["exitDate"] = pd.to_datetime(output["exitDate"], utc=True)
    return output.sort_values(["signalDate", "pair", "setupName"]).reset_index(drop=True)
