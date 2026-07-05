"""AlphaPilot Low Frequency Directional 4H V0.1 research strategy.

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
except ModuleNotFoundError:  # Allows local static compilation without Freqtrade.
    class IStrategy:  # type: ignore[no-redef]
        pass


class AlphaPilotLowFrequencyDirectional4HV01(IStrategy):
    """Simple BTC/ETH/SOL 4h long/short directional research strategy."""

    INTERFACE_VERSION = 3

    strategy_id = "alpha_low_frequency_directional_4h_v01"
    strategy_name = "AlphaPilot Low Frequency Directional 4H V0.1"
    strategy_version = "0.1-v13.4.34"
    strategy_status = "research_backtest_only"

    timeframe = "4h"
    can_short = True

    stoploss = -0.03
    minimal_roi = {
        "0": 0.06,
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
        "direction": "long and short",
        "timeframe": "4h",
        "longScoreMinimum": 4,
        "shortScoreMinimum": 4,
        "stoploss": -0.03,
        "minimalRoi": 0.06,
        "noChaseLong": "recentReturn3Bars >= 10% blocks new longs",
        "noChaseShort": "recentReturn3Bars <= -10% blocks new shorts",
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

        previous_close = dataframe["close"].shift(1)
        high_low = dataframe["high"] - dataframe["low"]
        high_close = (dataframe["high"] - previous_close).abs()
        low_close = (dataframe["low"] - previous_close).abs()
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        dataframe["atr14"] = true_range.rolling(14, min_periods=14).mean()

        dataframe["volume_mean_20"] = dataframe["volume"].rolling(20, min_periods=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_mean_20"].replace(0, np.nan)
        dataframe["recent_return_3_bars"] = (dataframe["close"] / dataframe["close"].shift(3)) - 1
        return dataframe

    @staticmethod
    def _add_scores(dataframe: DataFrame) -> DataFrame:
        dataframe["ap_lf_audit_trend_up"] = (dataframe["close"] > dataframe["ema200"]) & (dataframe["ema20"] > dataframe["ema50"])
        dataframe["ap_lf_audit_pullback_reclaim"] = (
            ((dataframe["low"] <= dataframe["ema20"] * 1.015) | (dataframe["low"] <= dataframe["ema50"] * 1.015))
            & (dataframe["close"] > dataframe["ema20"])
        )
        dataframe["ap_lf_audit_long_momentum_improving"] = dataframe["macd_histogram"] > dataframe["macd_histogram"].shift(1)
        dataframe["ap_lf_audit_rsi_not_overheated"] = dataframe["rsi14"] < 65
        dataframe["ap_lf_audit_volume_healthy"] = dataframe["volume_ratio"] >= 0.8

        dataframe["ap_lf_audit_trend_down"] = (dataframe["close"] < dataframe["ema200"]) & (dataframe["ema20"] < dataframe["ema50"])
        dataframe["ap_lf_audit_failed_bounce"] = (
            ((dataframe["high"] >= dataframe["ema20"] * 0.985) | (dataframe["high"] >= dataframe["ema50"] * 0.985))
            & (dataframe["close"] < dataframe["ema20"])
        )
        dataframe["ap_lf_audit_short_momentum_weakening"] = dataframe["macd_histogram"] < dataframe["macd_histogram"].shift(1)
        dataframe["ap_lf_audit_rsi_not_oversold"] = dataframe["rsi14"] > 35

        long_score_columns = [
            "ap_lf_audit_trend_up",
            "ap_lf_audit_pullback_reclaim",
            "ap_lf_audit_long_momentum_improving",
            "ap_lf_audit_rsi_not_overheated",
            "ap_lf_audit_volume_healthy",
        ]
        short_score_columns = [
            "ap_lf_audit_trend_down",
            "ap_lf_audit_failed_bounce",
            "ap_lf_audit_short_momentum_weakening",
            "ap_lf_audit_rsi_not_oversold",
            "ap_lf_audit_volume_healthy",
        ]
        dataframe["ap_lf_audit_long_score"] = dataframe[long_score_columns].fillna(False).astype(int).sum(axis=1)
        dataframe["ap_lf_audit_short_score"] = dataframe[short_score_columns].fillna(False).astype(int).sum(axis=1)
        return dataframe

    @staticmethod
    def _add_blockers(dataframe: DataFrame) -> DataFrame:
        required_columns = [
            "ema20",
            "ema50",
            "ema200",
            "rsi14",
            "macd_histogram",
            "volume_ratio",
            "recent_return_3_bars",
        ]
        dataframe["ap_lf_audit_data_missing"] = dataframe[required_columns].isna().any(axis=1)
        dataframe["ap_lf_audit_no_chase_long"] = dataframe["recent_return_3_bars"] < 0.10
        dataframe["ap_lf_audit_no_chase_short"] = dataframe["recent_return_3_bars"] > -0.10
        return dataframe

    @staticmethod
    def _final_long_entry(dataframe: DataFrame) -> Any:
        return (
            (dataframe["ap_lf_audit_long_score"] >= 4)
            & dataframe["ap_lf_audit_no_chase_long"]
            & ~dataframe["ap_lf_audit_data_missing"]
            & (dataframe["volume"] > 0)
        )

    @staticmethod
    def _final_short_entry(dataframe: DataFrame) -> Any:
        return (
            (dataframe["ap_lf_audit_short_score"] >= 4)
            & dataframe["ap_lf_audit_no_chase_short"]
            & ~dataframe["ap_lf_audit_data_missing"]
            & (dataframe["volume"] > 0)
        )

    @staticmethod
    def _add_audit_columns(dataframe: DataFrame) -> DataFrame:
        dataframe["ap_lf_audit_final_long_entry"] = AlphaPilotLowFrequencyDirectional4HV01._final_long_entry(dataframe)
        dataframe["ap_lf_audit_final_short_entry"] = AlphaPilotLowFrequencyDirectional4HV01._final_short_entry(dataframe)
        dataframe["ap_lf_audit_skip_reason"] = np.select(
            [
                dataframe["ap_lf_audit_final_long_entry"],
                dataframe["ap_lf_audit_final_short_entry"],
                dataframe["ap_lf_audit_data_missing"],
                ~dataframe["ap_lf_audit_no_chase_long"],
                ~dataframe["ap_lf_audit_no_chase_short"],
                dataframe["ap_lf_audit_long_score"] < 4,
                dataframe["ap_lf_audit_short_score"] < 4,
            ],
            [
                "entry_long_passed",
                "entry_short_passed",
                "data_missing",
                "chase_long",
                "chase_short",
                "long_score_too_low",
                "short_score_too_low",
            ],
            default="unknown",
        )
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe = self._add_core_indicators(dataframe)
        dataframe = self._add_scores(dataframe)
        dataframe = self._add_blockers(dataframe)
        return self._add_audit_columns(dataframe)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""
        long_condition = dataframe["ap_lf_audit_final_long_entry"]
        short_condition = dataframe["ap_lf_audit_final_short_entry"] & ~long_condition
        dataframe.loc[long_condition, "enter_long"] = 1
        dataframe.loc[long_condition, "enter_tag"] = "lf_4h_long_score"
        dataframe.loc[short_condition, "enter_short"] = 1
        dataframe.loc[short_condition, "enter_tag"] = "lf_4h_short_score"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        dataframe["exit_tag"] = ""
        return dataframe

    def _latest_histogram_values(self, pair: str, current_time: datetime) -> np.ndarray | None:
        if not getattr(self, "dp", None):
            return None
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        except Exception:
            return None
        if dataframe.empty or "date" not in dataframe.columns or "macd_histogram" not in dataframe.columns:
            return None
        rows = dataframe.loc[dataframe["date"] <= current_time].tail(3)
        if len(rows) < 3:
            return None
        values = rows["macd_histogram"].to_numpy()
        if not np.isfinite(values).all():
            return None
        return values

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
        if current_time.tzinfo is not None and open_date.tzinfo is None:
            open_date = open_date.replace(tzinfo=current_time.tzinfo)
        elif current_time.tzinfo is None and open_date.tzinfo is not None:
            current_time = current_time.replace(tzinfo=open_date.tzinfo)
        age_hours = (current_time - open_date).total_seconds() / 3600
        if age_hours >= 40 and current_profit <= 0:
            return "time_stop_10x4h_not_profitable"

        if current_profit <= 0:
            return None
        values = self._latest_histogram_values(pair, current_time)
        if values is None:
            return None
        is_short = bool(getattr(trade, "is_short", False))
        if is_short and values[-1] > values[-2] > values[-3]:
            return "profitable_short_momentum_exit"
        if not is_short and values[-1] < values[-2] < values[-3]:
            return "profitable_long_momentum_exit"
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
