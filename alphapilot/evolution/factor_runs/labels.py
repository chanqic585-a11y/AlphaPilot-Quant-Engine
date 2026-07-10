"""Conservative next-bar directional labels with a fixed >=2R target."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DirectionalLabelConfig:
    stopLossR: float = 1.0
    takeProfitR: float = 2.0
    maxHoldingBars: int = 12
    feeRate: float = 0.0005
    slippageRate: float = 0.0002

    def validate(self) -> None:
        if self.stopLossR <= 0 or self.takeProfitR / self.stopLossR < 2.0:
            raise ValueError("Directional labels require a reward/risk ratio of at least 2R")
        if self.maxHoldingBars <= 0:
            raise ValueError("maxHoldingBars must be positive")
        if self.feeRate < 0 or self.slippageRate < 0:
            raise ValueError("Fee and slippage rates must be non-negative")


def _simulate(
    frame: pd.DataFrame,
    risk_distance: pd.Series,
    *,
    direction: str,
    entry_delay: int,
    config: DirectionalLabelConfig,
) -> pd.DataFrame:
    if direction not in {"long", "short"}:
        raise ValueError("direction must be long or short")
    size = len(frame)
    values = {
        "available": np.zeros(size, dtype=bool),
        "target_hit": np.zeros(size, dtype="int8"),
        "outcome": np.full(size, "unavailable", dtype=object),
        "gross_r": np.full(size, np.nan),
        "net_r": np.full(size, np.nan),
        "gross_return": np.full(size, np.nan),
        "net_return": np.full(size, np.nan),
        "entry_price": np.full(size, np.nan),
        "exit_price": np.full(size, np.nan),
        "exit_timestamp_ms": np.full(size, np.nan),
        "same_bar_ambiguous": np.zeros(size, dtype=bool),
    }
    opens = pd.to_numeric(frame["open"], errors="coerce").to_numpy(dtype="float64")
    highs = pd.to_numeric(frame["high"], errors="coerce").to_numpy(dtype="float64")
    lows = pd.to_numeric(frame["low"], errors="coerce").to_numpy(dtype="float64")
    closes = pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype="float64")
    timestamps = pd.to_numeric(frame["timestamp_ms"], errors="coerce").to_numpy(dtype="float64")
    risks = pd.to_numeric(risk_distance, errors="coerce").to_numpy(dtype="float64")
    per_side_cost_rate = config.feeRate + config.slippageRate

    for decision_index in range(size):
        entry_index = decision_index + entry_delay
        final_index = entry_index + config.maxHoldingBars - 1
        if final_index >= size:
            continue
        entry_price = opens[entry_index]
        one_r = risks[decision_index] * config.stopLossR
        if not np.isfinite(entry_price) or entry_price <= 0 or not np.isfinite(one_r) or one_r <= 0:
            continue
        target_distance = one_r * (config.takeProfitR / config.stopLossR)
        if direction == "long":
            stop_price = entry_price - one_r
            target_price = entry_price + target_distance
        else:
            stop_price = entry_price + one_r
            target_price = entry_price - target_distance
        if stop_price <= 0 or target_price <= 0:
            continue

        exit_price = closes[final_index]
        exit_index = final_index
        outcome = "timeout"
        ambiguous = False
        for path_index in range(entry_index, final_index + 1):
            if direction == "long":
                stop_touched = lows[path_index] <= stop_price
                target_touched = highs[path_index] >= target_price
            else:
                stop_touched = highs[path_index] >= stop_price
                target_touched = lows[path_index] <= target_price
            if stop_touched:
                ambiguous = bool(target_touched)
                exit_price = stop_price
                exit_index = path_index
                outcome = "stop"
                break
            if target_touched:
                exit_price = target_price
                exit_index = path_index
                outcome = "target"
                break

        gross_amount = (
            exit_price - entry_price if direction == "long" else entry_price - exit_price
        )
        transaction_cost = (entry_price + exit_price) * per_side_cost_rate
        net_amount = gross_amount - transaction_cost
        values["available"][decision_index] = True
        values["target_hit"][decision_index] = int(outcome == "target")
        values["outcome"][decision_index] = outcome
        values["gross_r"][decision_index] = gross_amount / one_r
        values["net_r"][decision_index] = net_amount / one_r
        values["gross_return"][decision_index] = gross_amount / entry_price
        values["net_return"][decision_index] = net_amount / entry_price
        values["entry_price"][decision_index] = entry_price
        values["exit_price"][decision_index] = exit_price
        values["exit_timestamp_ms"][decision_index] = timestamps[exit_index]
        values["same_bar_ambiguous"][decision_index] = ambiguous
    return pd.DataFrame(values, index=frame.index)


def build_directional_labels(
    frame: pd.DataFrame,
    *,
    risk_distance: pd.Series,
    config: DirectionalLabelConfig | None = None,
) -> pd.DataFrame:
    settings = config or DirectionalLabelConfig()
    settings.validate()
    required = {"timestamp_ms", "open", "high", "low", "close"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing label fields: {', '.join(missing)}")
    output = pd.DataFrame(index=frame.index)
    for direction in ("long", "short"):
        normal = _simulate(
            frame,
            risk_distance,
            direction=direction,
            entry_delay=1,
            config=settings,
        ).add_prefix(f"label_{direction}_")
        delayed = _simulate(
            frame,
            risk_distance,
            direction=direction,
            entry_delay=2,
            config=settings,
        )
        delayed = delayed[["available", "gross_r", "net_r", "gross_return", "net_return"]].add_prefix(
            f"label_{direction}_delayed_"
        )
        output = pd.concat([output, normal, delayed], axis=1)
    return output
