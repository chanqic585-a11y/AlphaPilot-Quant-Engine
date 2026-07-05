"""AlphaPilot V13.4.23 benchmark strategies.

These classes are transparent research baselines only. They are not AlphaPilot
production strategies, not Dry-run candidates, not live-trading systems, and
they must not be connected to real API keys or exchange private endpoints.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from pandas import DataFrame

try:
    from freqtrade.strategy import IStrategy
except ModuleNotFoundError:  # Allows local static compilation without Freqtrade.
    class IStrategy:  # type: ignore[no-redef]
        pass


class _AlphaPilotBenchmarkBase(IStrategy):
    """Shared long-only benchmark indicator helpers."""

    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    startup_candle_count = 260
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    benchmark_status = "research_only"
    dry_run_approved = False
    live_trading_approved = False

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
        return dataframe

    @staticmethod
    def _add_td_setup(dataframe: DataFrame) -> DataFrame:
        down = dataframe["close"] < dataframe["close"].shift(4)
        setup = []
        count = 0
        for value in down.fillna(False):
            count = count + 1 if value else 0
            setup.append(count)
        dataframe["td_buy_setup_count"] = setup
        return dataframe

    def _merge_btc_context(self, dataframe: DataFrame) -> DataFrame:
        if not getattr(self, "dp", None):
            dataframe["btc_1h_return_3"] = np.nan
            dataframe["btc_context_available"] = False
            dataframe["btc_not_crashing"] = True
            return dataframe
        try:
            btc = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe="1h")
        except Exception:
            btc = DataFrame()
        if btc.empty or "date" not in btc.columns:
            dataframe["btc_1h_return_3"] = np.nan
            dataframe["btc_context_available"] = False
            dataframe["btc_not_crashing"] = True
            return dataframe
        btc = btc.copy()
        btc["btc_1h_return_3"] = (btc["close"] / btc["close"].shift(3)) - 1
        view = btc[["date", "btc_1h_return_3"]]
        dataframe = dataframe.merge(view, on="date", how="left")
        dataframe["btc_context_available"] = dataframe["btc_1h_return_3"].notna()
        dataframe["btc_not_crashing"] = dataframe["btc_1h_return_3"].isna() | (dataframe["btc_1h_return_3"] > -0.015)
        return dataframe

    def informative_pairs(self) -> list[tuple[str, str]]:
        return [("BTC/USDT:USDT", "1h")]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe = self._add_core_indicators(dataframe)
        dataframe = self._add_td_setup(dataframe)
        return self._merge_btc_context(dataframe)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = ""
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_tag"] = ""
        return dataframe

    def leverage(
        self,
        pair: str,
        current_time: Any,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        return min(5.0, max_leverage)


class BenchmarkEMATrend(_AlphaPilotBenchmarkBase):
    """Simple 1h EMA trend-following benchmark."""

    stoploss = -0.025
    minimal_roi = {"0": 0.05}

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["enter_long"] = 0
        condition = (
            (dataframe["ema20"] > dataframe["ema50"])
            & (dataframe["close"] > dataframe["ema20"])
            & (dataframe["macd_histogram"] > 0)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[condition, "enter_long"] = 1
        dataframe.loc[condition, "enter_tag"] = "benchmark_ema_trend"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["exit_long"] = 0
        condition = dataframe["close"] < dataframe["ema20"]
        dataframe.loc[condition, "exit_long"] = 1
        dataframe.loc[condition, "exit_tag"] = "benchmark_ema_trend_exit"
        return dataframe


class BenchmarkRSIMeanReversion(_AlphaPilotBenchmarkBase):
    """Simple RSI and Bollinger lower-band mean-reversion benchmark."""

    stoploss = -0.02
    minimal_roi = {"0": 0.025}

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["enter_long"] = 0
        condition = (
            (dataframe["rsi14"] < 30)
            & (dataframe["close"] <= dataframe["bb_lower"] * 1.01)
            & dataframe["btc_not_crashing"]
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[condition, "enter_long"] = 1
        dataframe.loc[condition, "enter_tag"] = "benchmark_rsi_mean_reversion"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["exit_long"] = 0
        condition = (dataframe["rsi14"] > 50) | (dataframe["close"] >= dataframe["bb_middle"])
        dataframe.loc[condition, "exit_long"] = 1
        dataframe.loc[condition, "exit_tag"] = "benchmark_rsi_recovery"
        return dataframe


class BenchmarkMACDVolume(_AlphaPilotBenchmarkBase):
    """Simple MACD momentum with volume confirmation benchmark."""

    stoploss = -0.025
    minimal_roi = {"0": 0.04}

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["enter_long"] = 0
        condition = (
            (dataframe["macd_histogram"] > dataframe["macd_histogram"].shift(1))
            & (dataframe["macd"] > dataframe["macd_signal"])
            & (dataframe["volume_ratio"] >= 1.2)
            & (dataframe["close"] > dataframe["ema50"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[condition, "enter_long"] = 1
        dataframe.loc[condition, "enter_tag"] = "benchmark_macd_volume"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["exit_long"] = 0
        weak_two = (
            (dataframe["macd_histogram"] < dataframe["macd_histogram"].shift(1))
            & (dataframe["macd_histogram"].shift(1) < dataframe["macd_histogram"].shift(2))
        )
        dataframe.loc[weak_two, "exit_long"] = 1
        dataframe.loc[weak_two, "exit_tag"] = "benchmark_macd_volume_weakness"
        return dataframe


class BenchmarkBollingerRebound(_AlphaPilotBenchmarkBase):
    """Simple Bollinger lower-band reclaim benchmark."""

    stoploss = -0.02
    minimal_roi = {"0": 0.025}

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["enter_long"] = 0
        reclaimed_lower = (dataframe["close"] > dataframe["bb_lower"]) & (dataframe["close"].shift(1) <= dataframe["bb_lower"].shift(1))
        condition = reclaimed_lower & (dataframe["rsi14"] < 45) & (dataframe["volume_ratio"] >= 0.7) & (dataframe["volume"] > 0)
        dataframe.loc[condition, "enter_long"] = 1
        dataframe.loc[condition, "enter_tag"] = "benchmark_bollinger_rebound"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["exit_long"] = 0
        condition = dataframe["close"] >= dataframe["bb_middle"]
        dataframe.loc[condition, "exit_long"] = 1
        dataframe.loc[condition, "exit_tag"] = "benchmark_bollinger_middle"
        return dataframe


class BenchmarkTD9Exhaustion(_AlphaPilotBenchmarkBase):
    """Simplified TD9-style exhaustion benchmark."""

    stoploss = -0.02
    minimal_roi = {"0": 0.03}

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["enter_long"] = 0
        condition = (
            (dataframe["td_buy_setup_count"] >= 9)
            & (dataframe["rsi14"] < 45)
            & dataframe["btc_not_crashing"]
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[condition, "enter_long"] = 1
        dataframe.loc[condition, "enter_tag"] = "benchmark_td9_exhaustion"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        dataframe["exit_long"] = 0
        condition = dataframe["rsi14"] > 50
        dataframe.loc[condition, "exit_long"] = 1
        dataframe.loc[condition, "exit_tag"] = "benchmark_td9_rsi_recovery"
        return dataframe
