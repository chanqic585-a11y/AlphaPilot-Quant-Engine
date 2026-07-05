"""AlphaPilot V13.4.35 low-frequency strategy batch.

本文件中的策略仅用于研究和回测。
不得用于 Dry-run。
不得用于实盘。
不得接真实 API Key。
不得自动交易。

The strategies use public historical OHLCV backtests only. They do not use
private exchange APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from pandas import DataFrame, Series

try:
    from freqtrade.strategy import IStrategy
except ModuleNotFoundError:  # Allows local static compilation without Freqtrade.
    class IStrategy:  # type: ignore[no-redef]
        pass


def _false_series(dataframe: DataFrame) -> Series:
    return pd.Series(False, index=dataframe.index)


class _AlphaPilotBatchBase(IStrategy):
    """Shared research-only indicator and exit logic for V13.4.35."""

    INTERFACE_VERSION = 3

    timeframe = "4h"
    can_short = False
    stoploss = -0.04
    minimal_roi = {"0": 0.08}

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    process_only_new_candles = True
    startup_candle_count = 260

    strategy_id = "alpha_batch_base"
    strategy_name = "AlphaPilot Batch Base"
    strategy_version = "0.1-v13.4.35"
    direction = "base"
    exit_at_bb_middle = False

    alphapilot_parameters = {
        "status": "research_backtest_only",
        "timeframe": "4h",
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
        dataframe["atr_pct"] = dataframe["atr14"] / dataframe["close"].replace(0, np.nan)
        dataframe["atr_pct_median_20"] = dataframe["atr_pct"].rolling(20, min_periods=20).median()

        dataframe["volume_mean_20"] = dataframe["volume"].rolling(20, min_periods=20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_mean_20"].replace(0, np.nan)
        dataframe["recent_return_3_bars"] = dataframe["close"].pct_change(3)
        dataframe["return_12_bars"] = dataframe["close"].pct_change(12)

        dataframe["recent_high_20"] = dataframe["high"].rolling(20, min_periods=20).max()
        dataframe["recent_low_20"] = dataframe["low"].rolling(20, min_periods=20).min()
        dataframe["prior_high_20"] = dataframe["high"].shift(2).rolling(20, min_periods=20).max()
        dataframe["prior_low_20"] = dataframe["low"].shift(2).rolling(20, min_periods=20).min()
        dataframe["range_high_20"] = dataframe["recent_high_20"]
        dataframe["range_low_20"] = dataframe["recent_low_20"]

        dataframe["bb_middle"] = dataframe["close"].rolling(20, min_periods=20).mean()
        bb_std = dataframe["close"].rolling(20, min_periods=20).std()
        dataframe["bb_upper"] = dataframe["bb_middle"] + (bb_std * 2)
        dataframe["bb_lower"] = dataframe["bb_middle"] - (bb_std * 2)
        dataframe["bb_bandwidth"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_middle"].replace(0, np.nan)
        dataframe["bb_bandwidth_median_20"] = dataframe["bb_bandwidth"].rolling(20, min_periods=20).median()
        return dataframe

    def _add_relative_strength(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["btc_return_12_bars"] = np.nan
        dataframe["relative_strength_available"] = False
        pair = str(metadata.get("pair") or "")
        if pair == "BTC/USDT:USDT":
            dataframe["btc_return_12_bars"] = dataframe["return_12_bars"]
            dataframe["relative_strength_available"] = True
            return dataframe
        if not getattr(self, "dp", None) or "date" not in dataframe.columns:
            return dataframe
        try:
            btc = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe=self.timeframe)
        except Exception:
            return dataframe
        if btc.empty or "date" not in btc.columns or "close" not in btc.columns:
            return dataframe
        btc_frame = btc[["date", "close"]].copy()
        btc_frame["btc_return_12_bars"] = btc_frame["close"].pct_change(12)
        btc_frame = btc_frame[["date", "btc_return_12_bars"]].dropna().sort_values("date")
        if btc_frame.empty:
            return dataframe
        original_index = dataframe.index
        merged = pd.merge_asof(
            dataframe.sort_values("date"),
            btc_frame,
            on="date",
            direction="backward",
        )
        merged.index = original_index
        if "btc_return_12_bars_y" in merged.columns:
            merged["btc_return_12_bars"] = merged["btc_return_12_bars_y"]
            merged = merged.drop(columns=[column for column in ("btc_return_12_bars_x", "btc_return_12_bars_y") if column in merged.columns])
        elif "btc_return_12_bars" not in merged.columns:
            merged["btc_return_12_bars"] = np.nan
        merged["relative_strength_available"] = merged["btc_return_12_bars"].notna()
        return merged

    @staticmethod
    def _required(dataframe: DataFrame, columns: list[str]) -> Series:
        return ~dataframe[columns].isna().any(axis=1)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe = self._add_core_indicators(dataframe)
        dataframe = self._add_relative_strength(dataframe, metadata)
        return dataframe

    def long_condition(self, dataframe: DataFrame) -> Series:
        return _false_series(dataframe)

    def short_condition(self, dataframe: DataFrame) -> Series:
        return _false_series(dataframe)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""
        long_condition = self.long_condition(dataframe)
        short_condition = self.short_condition(dataframe) & ~long_condition
        dataframe.loc[long_condition, "enter_long"] = 1
        dataframe.loc[long_condition, "enter_tag"] = self.strategy_id
        dataframe.loc[short_condition, "enter_short"] = 1
        dataframe.loc[short_condition, "enter_tag"] = self.strategy_id
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        dataframe["exit_tag"] = ""
        return dataframe

    def _latest_row(self, pair: str, current_time: datetime) -> dict[str, Any] | None:
        if not getattr(self, "dp", None):
            return None
        try:
            dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        except Exception:
            return None
        if dataframe.empty or "date" not in dataframe.columns:
            return None
        rows = dataframe.loc[dataframe["date"] <= current_time].tail(1)
        if rows.empty:
            return None
        return rows.iloc[-1].to_dict()

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

        if not self.exit_at_bb_middle or current_profit <= 0:
            return None
        row = self._latest_row(pair, current_time)
        if not row:
            return None
        middle = row.get("bb_middle")
        if middle is None or not np.isfinite(middle):
            return None
        if bool(getattr(trade, "is_short", False)):
            if current_rate <= middle:
                return "bb_middle_profit_exit"
        elif current_rate >= middle:
            return "bb_middle_profit_exit"
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


class AlphaPilotBatchA_EMATrendLong4H(_AlphaPilotBatchBase):
    strategy_id = "alpha_batch_a_ema_trend_long_4h"
    strategy_name = "AlphaPilot Batch A EMA Trend Long 4H"
    direction = "long_only"
    can_short = False
    stoploss = -0.04
    minimal_roi = {"0": 0.08}

    def long_condition(self, dataframe: DataFrame) -> Series:
        required = self._required(dataframe, ["ema20", "ema50", "ema200", "macd_histogram", "rsi14"])
        return (
            required
            & (dataframe["close"] > dataframe["ema200"])
            & (dataframe["ema20"] > dataframe["ema50"])
            & (dataframe["close"] > dataframe["ema20"])
            & (dataframe["macd_histogram"] > 0)
            & (dataframe["rsi14"] < 70)
        )


class AlphaPilotBatchB_EMATrendShort4H(_AlphaPilotBatchBase):
    strategy_id = "alpha_batch_b_ema_trend_short_4h"
    strategy_name = "AlphaPilot Batch B EMA Trend Short 4H"
    direction = "short_only"
    can_short = True
    stoploss = -0.04
    minimal_roi = {"0": 0.08}

    def short_condition(self, dataframe: DataFrame) -> Series:
        required = self._required(dataframe, ["ema20", "ema50", "ema200", "macd_histogram", "rsi14"])
        return (
            required
            & (dataframe["close"] < dataframe["ema200"])
            & (dataframe["ema20"] < dataframe["ema50"])
            & (dataframe["close"] < dataframe["ema20"])
            & (dataframe["macd_histogram"] < 0)
            & (dataframe["rsi14"] > 30)
        )


class AlphaPilotBatchC_BreakoutRetestLong4H(_AlphaPilotBatchBase):
    strategy_id = "alpha_batch_c_breakout_retest_long_4h"
    strategy_name = "AlphaPilot Batch C Breakout Retest Long 4H"
    direction = "long_only"
    can_short = False
    stoploss = -0.04
    minimal_roi = {"0": 0.08}

    def long_condition(self, dataframe: DataFrame) -> Series:
        required = self._required(dataframe, ["prior_high_20", "volume_ratio", "recent_return_3_bars"])
        breakout_level = dataframe["prior_high_20"]
        return (
            required
            & (dataframe["close"].shift(1) > breakout_level)
            & (dataframe["low"] <= breakout_level * 1.02)
            & (dataframe["close"] > breakout_level)
            & (dataframe["volume_ratio"] >= 0.8)
            & (dataframe["recent_return_3_bars"] < 0.12)
        )


class AlphaPilotBatchD_BreakdownRetestShort4H(_AlphaPilotBatchBase):
    strategy_id = "alpha_batch_d_breakdown_retest_short_4h"
    strategy_name = "AlphaPilot Batch D Breakdown Retest Short 4H"
    direction = "short_only"
    can_short = True
    stoploss = -0.04
    minimal_roi = {"0": 0.08}

    def short_condition(self, dataframe: DataFrame) -> Series:
        required = self._required(dataframe, ["prior_low_20", "volume_ratio", "recent_return_3_bars"])
        breakdown_level = dataframe["prior_low_20"]
        return (
            required
            & (dataframe["close"].shift(1) < breakdown_level)
            & (dataframe["high"] >= breakdown_level * 0.98)
            & (dataframe["close"] < breakdown_level)
            & (dataframe["volume_ratio"] >= 0.8)
            & (dataframe["recent_return_3_bars"] > -0.12)
        )


class AlphaPilotBatchE_BollingerReversionLong4H(_AlphaPilotBatchBase):
    strategy_id = "alpha_batch_e_bollinger_reversion_long_4h"
    strategy_name = "AlphaPilot Batch E Bollinger Reversion Long 4H"
    direction = "long_only"
    can_short = False
    stoploss = -0.03
    minimal_roi = {"0": 0.05}
    exit_at_bb_middle = True

    def long_condition(self, dataframe: DataFrame) -> Series:
        required = self._required(dataframe, ["bb_lower", "rsi14", "volume_ratio", "recent_return_3_bars"])
        return (
            required
            & (dataframe["close"].shift(1) < dataframe["bb_lower"].shift(1))
            & (dataframe["close"] > dataframe["bb_lower"])
            & (dataframe["rsi14"] < 45)
            & (dataframe["volume_ratio"] >= 0.7)
            & (dataframe["recent_return_3_bars"] > -0.12)
        )


class AlphaPilotBatchF_BollingerReversionShort4H(_AlphaPilotBatchBase):
    strategy_id = "alpha_batch_f_bollinger_reversion_short_4h"
    strategy_name = "AlphaPilot Batch F Bollinger Reversion Short 4H"
    direction = "short_only"
    can_short = True
    stoploss = -0.03
    minimal_roi = {"0": 0.05}
    exit_at_bb_middle = True

    def short_condition(self, dataframe: DataFrame) -> Series:
        required = self._required(dataframe, ["bb_upper", "rsi14", "volume_ratio", "recent_return_3_bars"])
        return (
            required
            & (dataframe["close"].shift(1) > dataframe["bb_upper"].shift(1))
            & (dataframe["close"] < dataframe["bb_upper"])
            & (dataframe["rsi14"] > 55)
            & (dataframe["volume_ratio"] >= 0.7)
            & (dataframe["recent_return_3_bars"] < 0.12)
        )


class AlphaPilotBatchG_RelativeStrengthLong4H(_AlphaPilotBatchBase):
    strategy_id = "alpha_batch_g_relative_strength_long_4h"
    strategy_name = "AlphaPilot Batch G Relative Strength Long 4H"
    direction = "long_only"
    can_short = False
    stoploss = -0.04
    minimal_roi = {"0": 0.08}

    def long_condition(self, dataframe: DataFrame) -> Series:
        required = self._required(dataframe, ["ema20", "ema50", "rsi14", "macd_histogram", "return_12_bars"])
        btc_available = dataframe["relative_strength_available"].fillna(False).astype(bool)
        relative_strength_pass = (
            btc_available & (dataframe["return_12_bars"] > dataframe["btc_return_12_bars"])
        ) | (~btc_available & (dataframe["close"] > dataframe["ema50"]))
        return (
            required
            & relative_strength_pass
            & (dataframe["close"] > dataframe["ema50"])
            & (dataframe["ema20"] > dataframe["ema50"])
            & (dataframe["macd_histogram"] > dataframe["macd_histogram"].shift(1))
            & (dataframe["rsi14"] < 70)
        )


class AlphaPilotBatchH_VolatilityCompressionBreakout4H(_AlphaPilotBatchBase):
    strategy_id = "alpha_batch_h_volatility_compression_breakout_4h"
    strategy_name = "AlphaPilot Batch H Volatility Compression Breakout 4H"
    direction = "long_only"
    can_short = False
    stoploss = -0.04
    minimal_roi = {"0": 0.10}

    def long_condition(self, dataframe: DataFrame) -> Series:
        required = self._required(
            dataframe,
            [
                "atr_pct",
                "atr_pct_median_20",
                "bb_bandwidth",
                "bb_bandwidth_median_20",
                "prior_high_20",
                "volume_ratio",
                "rsi14",
            ],
        )
        return (
            required
            & (dataframe["atr_pct"] < dataframe["atr_pct_median_20"])
            & (dataframe["bb_bandwidth"] < dataframe["bb_bandwidth_median_20"])
            & (dataframe["close"] > dataframe["prior_high_20"])
            & (dataframe["volume_ratio"] >= 1.0)
            & (dataframe["rsi14"] < 75)
        )
