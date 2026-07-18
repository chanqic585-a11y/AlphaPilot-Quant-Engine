"""Pure S01 calculations shared by the Freqtrade research adapter."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd


S01_CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"


def _aligned(values: pd.Series, dates: pd.Series) -> pd.Series:
    return values.reindex(pd.DatetimeIndex(dates)).ffill().reset_index(drop=True)


def _rolling_z(values: pd.Series, window: int) -> pd.Series:
    mean = values.rolling(window, min_periods=window).mean()
    standard = values.rolling(window, min_periods=window).std(ddof=0).replace(0, np.nan)
    return (values - mean) / standard


def s01_indicator_frame(
    *,
    frame: pd.DataFrame,
    btc_close: pd.Series,
    market_close: pd.Series,
    feature_definition: Mapping[str, Any],
) -> pd.DataFrame:
    """Return the frozen causal indicators used by S01."""

    if str(feature_definition["marketRegime"]) != "btc_close_below_ema_200":
        raise ValueError("unsupported S01 market regime")
    close = pd.to_numeric(frame["close"], errors="coerce").reset_index(drop=True)
    btc = _aligned(btc_close, frame["date"])
    market = _aligned(market_close, frame["date"])
    residual = close.pct_change() - market.pct_change()
    window = int(feature_definition["residualWindow"])
    recovery_bars = int(feature_definition["recoveryBars"])
    residual_z = _rolling_z(residual, window)
    recovery_steps = residual_z.diff() > 0
    complete_recovery = (
        recovery_steps.rolling(recovery_bars, min_periods=recovery_bars).sum()
        == recovery_bars
    )
    return pd.DataFrame(
        {
            "s01_residual_z": residual_z,
            "s01_recovery_size": residual_z - residual_z.shift(recovery_bars),
            "s01_complete_recovery": complete_recovery.fillna(False),
            "s01_btc_close": btc,
            "s01_btc_ema_200": btc.ewm(
                span=200, adjust=False, min_periods=200
            ).mean(),
        },
        index=frame.index,
    )


def s01_entry_mask(
    *,
    frame: pd.DataFrame,
    btc_close: pd.Series,
    market_close: pd.Series,
    feature_definition: Mapping[str, Any],
    entry_definition: Mapping[str, Any],
) -> pd.Series:
    indicators = s01_indicator_frame(
        frame=frame,
        btc_close=btc_close,
        market_close=market_close,
        feature_definition=feature_definition,
    )
    recovery_bars = int(feature_definition["recoveryBars"])
    condition = (
        (
            indicators["s01_residual_z"].shift(recovery_bars)
            <= float(feature_definition["residualZMaximum"])
        )
        & indicators["s01_complete_recovery"]
        & (
            indicators["s01_recovery_size"]
            >= float(entry_definition["minimumRecoveryZ"])
        )
        & (indicators["s01_btc_close"] < indicators["s01_btc_ema_200"])
    )
    return condition.fillna(False).astype(bool)


def s01_structure_exit_mask(indicators: pd.DataFrame) -> pd.Series:
    """Frozen residual-neutral exit for the post-partial remainder."""

    return indicators["s01_residual_z"].abs().le(0.35).fillna(False)
