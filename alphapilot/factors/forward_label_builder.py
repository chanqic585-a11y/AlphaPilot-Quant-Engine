"""Forward label builder for V13.4.22 factor evaluation.

The labels in this module are forward-looking by definition, but they are
evaluation targets only. They must never be used to construct factor values,
filter the factor panel, alter the universe, create orders, or approve Dry-run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ForwardLabelConfig:
    horizons: list[int] = field(default_factory=lambda: [4, 8, 12, 24])
    tpPct: float = 0.05
    slPct: float = 0.025
    timeframe: str = "1h"


@dataclass
class ForwardLabelBuildResult:
    panel: pd.DataFrame
    labelColumns: list[str]
    validLabelCount: int
    horizonCoverage: dict[str, dict[str, Any]]
    warnings: list[str]
    generatedAt: str


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _tp_sl_first_touch(
    close_price: float,
    future_highs: pd.Series,
    future_lows: pd.Series,
    tp_pct: float,
    sl_pct: float,
) -> tuple[bool, bool, str | None]:
    tp_price = close_price * (1 + tp_pct)
    sl_price = close_price * (1 - sl_pct)
    for high_value, low_value in zip(future_highs, future_lows, strict=False):
        hit_tp = float(high_value) >= tp_price
        hit_sl = float(low_value) <= sl_price
        if hit_tp and hit_sl:
            return False, True, "tp_sl_same_bar_conservative_sl_first"
        if hit_tp:
            return True, False, None
        if hit_sl:
            return False, True, None
    return False, False, None


def _empty_label_frame(panel: pd.DataFrame, config: ForwardLabelConfig) -> ForwardLabelBuildResult:
    output = panel.copy()
    label_columns: list[str] = []
    for horizon in config.horizons:
        for prefix in ("forwardReturn", "mfePct", "maePct", "hitTpBeforeSl", "hitSlBeforeTp"):
            column = f"{prefix}_{horizon}"
            label_columns.append(column)
            output[column] = pd.NA
    return ForwardLabelBuildResult(
        panel=output,
        labelColumns=label_columns,
        validLabelCount=0,
        horizonCoverage={str(horizon): {"validForwardReturnCount": 0, "coveragePct": 0.0} for horizon in config.horizons},
        warnings=["Input factor panel was empty; forward labels were not generated."],
        generatedAt=utc_now(),
    )


def build_forward_labels(panel: pd.DataFrame, config: ForwardLabelConfig | None = None) -> ForwardLabelBuildResult:
    config = config or ForwardLabelConfig()
    if panel.empty:
        return _empty_label_frame(panel, config)

    required_columns = {"timestamp", "pair", "high", "low", "close"}
    missing = sorted(required_columns.difference(panel.columns))
    if missing:
        return ForwardLabelBuildResult(
            panel=panel.copy(),
            labelColumns=[],
            validLabelCount=0,
            horizonCoverage={},
            warnings=[f"Forward labels blocked because required columns are missing: {', '.join(missing)}"],
            generatedAt=utc_now(),
        )

    output = panel.copy().sort_values(["pair", "timestamp"]).reset_index(drop=True)
    label_columns: list[str] = []
    warnings: list[str] = [
        "Forward labels are evaluation targets only and do not feed back into factor computation.",
        "Same-bar TP/SL collisions are handled conservatively as SL-first for label accounting.",
    ]
    same_bar_collision_count = 0

    for horizon in config.horizons:
        forward_column = f"forwardReturn_{horizon}"
        mfe_column = f"mfePct_{horizon}"
        mae_column = f"maePct_{horizon}"
        tp_column = f"hitTpBeforeSl_{horizon}"
        sl_column = f"hitSlBeforeTp_{horizon}"
        label_columns.extend([forward_column, mfe_column, mae_column, tp_column, sl_column])
        output[forward_column] = pd.NA
        output[mfe_column] = pd.NA
        output[mae_column] = pd.NA
        output[tp_column] = pd.NA
        output[sl_column] = pd.NA

    for _, pair_frame in output.groupby("pair", sort=False):
        indices = list(pair_frame.index)
        closes = pair_frame["close"].astype(float).reset_index(drop=True)
        highs = pair_frame["high"].astype(float).reset_index(drop=True)
        lows = pair_frame["low"].astype(float).reset_index(drop=True)
        row_count = len(pair_frame)

        for local_idx, frame_idx in enumerate(indices):
            close_price = float(closes.iloc[local_idx])
            if close_price <= 0:
                continue
            for horizon in config.horizons:
                end_idx = local_idx + horizon
                if end_idx >= row_count:
                    continue
                future_highs = highs.iloc[local_idx + 1 : end_idx + 1]
                future_lows = lows.iloc[local_idx + 1 : end_idx + 1]
                future_close = float(closes.iloc[end_idx])

                forward_return = (future_close / close_price) - 1
                mfe_pct = (float(future_highs.max()) / close_price) - 1 if not future_highs.empty else pd.NA
                mae_pct = (float(future_lows.min()) / close_price) - 1 if not future_lows.empty else pd.NA
                hit_tp, hit_sl, collision = _tp_sl_first_touch(close_price, future_highs, future_lows, config.tpPct, config.slPct)
                if collision:
                    same_bar_collision_count += 1

                output.at[frame_idx, f"forwardReturn_{horizon}"] = forward_return
                output.at[frame_idx, f"mfePct_{horizon}"] = mfe_pct
                output.at[frame_idx, f"maePct_{horizon}"] = mae_pct
                output.at[frame_idx, f"hitTpBeforeSl_{horizon}"] = hit_tp
                output.at[frame_idx, f"hitSlBeforeTp_{horizon}"] = hit_sl

    horizon_coverage: dict[str, dict[str, Any]] = {}
    for horizon in config.horizons:
        column = f"forwardReturn_{horizon}"
        valid_count = int(pd.to_numeric(output[column], errors="coerce").notna().sum())
        horizon_coverage[str(horizon)] = {
            "validForwardReturnCount": valid_count,
            "rowCount": int(len(output)),
            "coveragePct": round((valid_count / len(output)) * 100, 4) if len(output) else 0.0,
        }
    valid_label_count = int(pd.to_numeric(output[f"forwardReturn_{max(config.horizons)}"], errors="coerce").notna().sum())
    if same_bar_collision_count:
        warnings.append(f"Conservative same-bar TP/SL collision count: {same_bar_collision_count}.")

    return ForwardLabelBuildResult(
        panel=output,
        labelColumns=label_columns,
        validLabelCount=valid_label_count,
        horizonCoverage=horizon_coverage,
        warnings=warnings,
        generatedAt=utc_now(),
    )
