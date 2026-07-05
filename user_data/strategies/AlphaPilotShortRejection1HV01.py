"""AlphaPilot Short Rejection 1H V0.1 research strategy.

本策略仅用于研究和回测。
不得用于 Dry-run。
不得用于实盘。
不得接真实 API Key。
不得自动交易。

The strategy uses public historical OHLCV backtests only. It does not use
private exchange APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
from pandas import DataFrame

try:
    from freqtrade.strategy import IStrategy
except ModuleNotFoundError:  # Allows local static import without Freqtrade.
    class IStrategy:  # type: ignore[no-redef]
        pass


class AlphaPilotShortRejection1HV01(IStrategy):
    """Short-only rejection research strategy."""

    INTERFACE_VERSION = 3

    strategy_id = "alpha_short_rejection_1h_v01"
    strategy_name = "AlphaPilot Short Rejection 1H V0.1"
    strategy_version = "0.1-v13.4.29"
    strategy_status = "research_backtest_only"

    timeframe = "1h"
    can_short = True

    stoploss = -0.025
    minimal_roi = {
        "0": 0.05,
    }

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count = 260
    process_only_new_candles = True

    alphapilot_parameters = {
        "strategyId": strategy_id,
        "strategyName": strategy_name,
        "status": strategy_status,
        "market": "OKX USDT swap",
        "direction": "short only",
        "timeframe": "1h",
        "shortScoreMinimum": 4,
        "stoploss": -0.025,
        "minimalRoi": 0.05,
        "noChaseAfterLargeDrop": "recentReturn12h <= -8% blocks new shorts",
        "extremeAtrBlocker": "atr_pct > 10% blocks new shorts",
        "dryRunApproved": False,
        "liveTradingApproved": False,
    }

    @staticmethod
    def _add_core_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe["ema20"] = dataframe["close"].ewm(span=20, adjust=False).mean()
        dataframe["ema50"] = dataframe["close"].ewm(span=50, adjust=False).mean()
        dataframe["ema200"] = dataframe["close"].ewm(span=200, adjust=False).mean()

        delta = dataframe["close"].diff()
        gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
        loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
        rs = gain / loss.replace(0, np.nan)
        dataframe["rsi14"] = 100 - (100 / (1 + rs))

        ema12 = dataframe["close"].ewm(span=12, adjust=False).mean()
        ema26 = dataframe["close"].ewm(span=26, adjust=False).mean()
        dataframe["macd"] = ema12 - ema26
        dataframe["macd_signal"] = dataframe["macd"].ewm(span=9, adjust=False).mean()
        dataframe["macd_histogram"] = dataframe["macd"] - dataframe["macd_signal"]

        dataframe["volume_mean_20"] = dataframe["volume"].rolling(20, min_periods=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_mean_20"].replace(0, np.nan)

        middle = dataframe["close"].rolling(20, min_periods=20).mean()
        std = dataframe["close"].rolling(20, min_periods=20).std()
        dataframe["bb_middle"] = middle
        dataframe["bb_upper"] = middle + std * 2
        dataframe["bb_lower"] = middle - std * 2

        previous_close = dataframe["close"].shift(1)
        high_low = dataframe["high"] - dataframe["low"]
        high_close = (dataframe["high"] - previous_close).abs()
        low_close = (dataframe["low"] - previous_close).abs()
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        dataframe["atr14"] = true_range.rolling(14, min_periods=14).mean()
        dataframe["atr_pct"] = dataframe["atr14"] / dataframe["close"].replace(0, np.nan)

        dataframe["recent_return_12h"] = (dataframe["close"] / dataframe["close"].shift(12)) - 1
        return dataframe

    @staticmethod
    def _add_short_score(dataframe: DataFrame) -> DataFrame:
        dataframe["ap_short_audit_rejection_area"] = (
            (dataframe["high"] >= dataframe["ema20"] * 0.995)
            | (dataframe["high"] >= dataframe["ema50"] * 0.995)
        )
        dataframe["ap_short_audit_close_below_ema20"] = dataframe["close"] < dataframe["ema20"]
        dataframe["ap_short_audit_macd_weakening"] = dataframe["macd_histogram"] < dataframe["macd_histogram"].shift(1)
        dataframe["ap_short_audit_rsi_weak"] = (dataframe["rsi14"] < 55) & (dataframe["rsi14"] < dataframe["rsi14"].shift(1))
        dataframe["ap_short_audit_volume_confirm"] = dataframe["volume_ratio"] >= 1.0

        score_columns = [
            "ap_short_audit_rejection_area",
            "ap_short_audit_close_below_ema20",
            "ap_short_audit_macd_weakening",
            "ap_short_audit_rsi_weak",
            "ap_short_audit_volume_confirm",
        ]
        dataframe["ap_short_audit_short_score"] = dataframe[score_columns].fillna(False).astype(int).sum(axis=1)
        return dataframe

    @staticmethod
    def _add_blockers(dataframe: DataFrame) -> DataFrame:
        required_columns = [
            "ema20",
            "ema50",
            "rsi14",
            "macd_histogram",
            "volume_ratio",
            "atr_pct",
            "recent_return_12h",
        ]
        dataframe["ap_short_audit_data_missing"] = dataframe[required_columns].isna().any(axis=1)
        dataframe["ap_short_audit_no_chase"] = dataframe["recent_return_12h"] > -0.08
        dataframe["ap_short_audit_extreme_atr"] = dataframe["atr_pct"] > 0.10
        return dataframe

    @staticmethod
    def _final_short_entry(dataframe: DataFrame) -> Any:
        return (
            (dataframe["ap_short_audit_short_score"] >= 4)
            & dataframe["ap_short_audit_no_chase"]
            & ~dataframe["ap_short_audit_extreme_atr"]
            & ~dataframe["ap_short_audit_data_missing"]
            & (dataframe["volume"] > 0)
        )

    @staticmethod
    def _add_audit_columns(dataframe: DataFrame) -> DataFrame:
        dataframe["ap_short_audit_final_short_entry"] = AlphaPilotShortRejection1HV01._final_short_entry(dataframe)
        dataframe["ap_short_audit_skip_reason"] = np.select(
            [
                dataframe["ap_short_audit_final_short_entry"],
                dataframe["ap_short_audit_data_missing"],
                ~dataframe["ap_short_audit_no_chase"],
                dataframe["ap_short_audit_extreme_atr"],
                dataframe["ap_short_audit_short_score"] < 4,
            ],
            [
                "entry_signal_passed",
                "data_missing",
                "chase_after_large_drop",
                "extreme_atr",
                "score_too_low",
            ],
            default="unknown",
        )
        dataframe["ap_short_audit_ema20"] = dataframe["ema20"]
        dataframe["ap_short_audit_ema50"] = dataframe["ema50"]
        dataframe["ap_short_audit_ema200"] = dataframe["ema200"]
        dataframe["ap_short_audit_rsi14"] = dataframe["rsi14"]
        dataframe["ap_short_audit_macd_histogram"] = dataframe["macd_histogram"]
        dataframe["ap_short_audit_volume_ratio"] = dataframe["volume_ratio"]
        dataframe["ap_short_audit_atr_pct"] = dataframe["atr_pct"]
        dataframe["ap_short_audit_recent_return_12h"] = dataframe["recent_return_12h"]
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe = self._add_core_indicators(dataframe)
        dataframe = self._add_short_score(dataframe)
        dataframe = self._add_blockers(dataframe)
        return self._add_audit_columns(dataframe)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""
        condition = dataframe["ap_short_audit_final_short_entry"]
        dataframe.loc[condition, "enter_short"] = 1
        dataframe.loc[condition, "enter_tag"] = "short_rejection_score"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["exit_short"] = 0
        dataframe["exit_tag"] = ""
        return dataframe

    def _profitable_short_momentum_exit(self, pair: str, current_time: datetime) -> bool:
        if not getattr(self, "dp", None):
            return False
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        except Exception:
            return False
        if dataframe.empty or "date" not in dataframe.columns or "macd_histogram" not in dataframe.columns:
            return False
        rows = dataframe.loc[dataframe["date"] <= current_time].tail(3)
        if len(rows) < 3:
            return False
        hist = rows["macd_histogram"].to_numpy()
        return bool(np.isfinite(hist).all() and hist[-1] > hist[-2] > hist[-3])

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
        age_hours = (current_time - open_date).total_seconds() / 3600
        if age_hours >= 8 and current_profit <= 0:
            return "short_time_stop_8h_not_profitable"
        if current_profit > 0 and self._profitable_short_momentum_exit(pair, current_time):
            return "profitable_short_momentum_exit"
        return None

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        return min(5.0, max_leverage)
