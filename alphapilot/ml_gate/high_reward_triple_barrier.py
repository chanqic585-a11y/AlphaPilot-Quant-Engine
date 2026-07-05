"""Triple-barrier labels for V13.5.6 high-reward events."""

from __future__ import annotations

import numpy as np
import pandas as pd

from alphapilot.ml_gate.high_reward_event_setups import HIGH_REWARD_SETUP_NAMES, add_high_reward_event_setups
from alphapilot.ml_gate.triple_barrier import BarrierConfig

try:
    from alphapilot.factors.alpha101_style_overlay import ALPHA101_STYLE_FACTOR_COLUMNS
except ImportError:  # pragma: no cover - optional research overlay
    ALPHA101_STYLE_FACTOR_COLUMNS = []


HIGH_REWARD_FEATURE_COLUMNS = [
    "pair",
    "date",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "return_3",
    "return_6",
    "return_12",
    "ema20_gap",
    "ema200_gap",
    "ema20_slope_6",
    "ema50_slope_6",
    "rsi14",
    "atr_pct",
    "range_pct",
    "body_pct",
    "upper_wick_pct",
    "lower_wick_pct",
    "close_location",
    "volume_ratio",
    "bollinger_z",
    "support_distance_pct",
    "resistance_distance_pct",
    "prior_high_48",
    "prior_low_48",
    "breakout_above_48_pct",
    "breakdown_below_48_pct",
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
    *ALPHA101_STYLE_FACTOR_COLUMNS,
]


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

    final_position = min(entry_position + config.horizon_bars, len(pair_frame) - 1)
    exit_price = float(pair_frame.iloc[final_position]["close"])
    exit_date = pair_frame.iloc[final_position]["date"]
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


def build_high_reward_labeled_events(
    panel: pd.DataFrame,
    config: BarrierConfig,
    setups: list[str] | None = None,
) -> pd.DataFrame:
    setup_names = setups or HIGH_REWARD_SETUP_NAMES
    prepared = panel.copy() if all(name in panel.columns for name in setup_names) else add_high_reward_event_setups(panel)
    events: list[dict[str, object]] = []
    for pair, pair_frame in prepared.groupby("pair", sort=False):
        pair_frame = pair_frame.sort_values("date").reset_index(drop=True)
        available_setups = [name for name in setup_names if name in pair_frame.columns]
        if not available_setups:
            continue
        signal_positions = pair_frame.index[pair_frame[available_setups].fillna(False).any(axis=1)].tolist()
        for position in signal_positions:
            row = pair_frame.iloc[position]
            active_setups = [name for name in available_setups if bool(row.get(name, False))]
            for setup_name in active_setups:
                direction = "short" if setup_name.startswith("hr_short") else "long"
                outcome = _simulate_one(pair_frame, position, direction, config)
                if outcome is None:
                    continue
                event = {column: row.get(column) for column in HIGH_REWARD_FEATURE_COLUMNS}
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
