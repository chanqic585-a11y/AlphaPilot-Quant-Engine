"""AlphaPilot Volume Rebound V0.2 candidate strategies.

These classes are candidate_only backtest variants for V13.4.4 comparative
research. They are not configured as default strategies, not approved for
Dry-run, not live strategies, and do not create real orders.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from typing import Any

import numpy as np
from pandas import DataFrame

STRATEGY_DIR = Path(__file__).resolve().parent
if str(STRATEGY_DIR) not in sys.path:
    sys.path.append(str(STRATEGY_DIR))

from AlphaPilotVolumeReboundV01 import AlphaPilotVolumeReboundV01  # noqa: E402


class AlphaPilotVolumeReboundV02ATrendStrict(AlphaPilotVolumeReboundV01):
    """candidate_only: stricter 4h trend filter."""

    strategy_id = "alpha_volume_rebound_v02_a_trend_strict"
    strategy_version = "0.2A-candidate-v13.4.4"

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        dataframe["trend_4h_ok"] = (
            dataframe["close_4h"].notna()
            & dataframe["ema200_4h"].notna()
            & (dataframe["close_4h"] >= dataframe["ema200_4h"])
        )
        dataframe["skip_weak_4h_trend"] = ~dataframe["trend_4h_ok"]
        return self._add_audit_columns(dataframe)


class AlphaPilotVolumeReboundV02BVolumeQuality(AlphaPilotVolumeReboundV01):
    """candidate_only: require stronger volume ratio."""

    strategy_id = "alpha_volume_rebound_v02_b_volume_quality"
    strategy_version = "0.2B-candidate-v13.4.4"

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_indicators(dataframe, metadata)
        dataframe["volume_rebound_ok"] = dataframe["volume_ratio"] >= 2.0
        dataframe["skip_volume_ratio_too_low"] = ~dataframe["volume_rebound_ok"]
        return self._add_audit_columns(dataframe)


class AlphaPilotVolumeReboundV02CExitCleanup(AlphaPilotVolumeReboundV01):
    """candidate_only: use MACD weakness only as a positive-profit exit."""

    strategy_id = "alpha_volume_rebound_v02_c_exit_cleanup"
    strategy_version = "0.2C-candidate-v13.4.4"

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_tag"] = ""
        return dataframe

    def _current_macd_weak(self, pair: str, current_time: datetime) -> bool:
        if not getattr(self, "dp", None):
            return False
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        except Exception:
            return False
        if dataframe.empty or "date" not in dataframe.columns or "macd_histogram" not in dataframe.columns:
            return False
        current_rows = dataframe.loc[dataframe["date"] <= current_time].tail(3)
        if len(current_rows) < 3:
            return False
        hist = current_rows["macd_histogram"].to_numpy()
        return bool(np.isfinite(hist).all() and hist[-1] < hist[-2] < hist[-3])

    def custom_exit(
        self,
        pair: str,
        trade: Any,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs: Any,
    ) -> str | None:
        open_date = getattr(trade, "open_date_utc", None)
        if open_date is None:
            return None

        age_minutes = (current_time - open_date).total_seconds() / 60
        if age_minutes >= 12 * 15 and current_profit <= 0:
            return "time_stop_12_candles_no_profit"
        if current_profit > 0 and self._current_macd_weak(pair, current_time):
            return "macd_histogram_two_candle_weakness_profit_only"
        return None


class AlphaPilotVolumeReboundV02DEarlyFailureExit(AlphaPilotVolumeReboundV01):
    """candidate_only: earlier no-profit time stop after 6 closed 15m candles."""

    strategy_id = "alpha_volume_rebound_v02_d_early_failure_exit"
    strategy_version = "0.2D-candidate-v13.4.4"

    def custom_exit(
        self,
        pair: str,
        trade: Any,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs: Any,
    ) -> str | None:
        open_date = getattr(trade, "open_date_utc", None)
        if open_date is None:
            return None

        age_minutes = (current_time - open_date).total_seconds() / 60
        if age_minutes >= 6 * 15 and current_profit <= 0:
            return "time_stop_6_candles_no_profit"
        return None


class AlphaPilotVolumeReboundV02EPairRiskWatchlist(AlphaPilotVolumeReboundV01):
    """candidate_only: cap SOL to the first signal per UTC day."""

    strategy_id = "alpha_volume_rebound_v02_e_pair_risk_watchlist"
    strategy_version = "0.2E-candidate-v13.4.4"

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = super().populate_entry_trend(dataframe, metadata)
        if metadata.get("pair") != "SOL/USDT:USDT" or "date" not in dataframe.columns:
            return dataframe

        entry_flags = dataframe["enter_long"].fillna(0).astype(int)
        entry_date = dataframe["date"].dt.strftime("%Y-%m-%d")
        daily_entry_count = entry_flags.groupby(entry_date).cumsum()
        blocked = (entry_flags == 1) & (daily_entry_count > 1)
        dataframe.loc[blocked, "enter_long"] = 0
        dataframe.loc[blocked, "enter_tag"] = "pair_risk_daily_cap_blocked"
        dataframe.loc[(entry_flags == 1) & ~blocked, "enter_tag"] = "volume_rebound_v02_e_pair_daily_cap"
        return dataframe

