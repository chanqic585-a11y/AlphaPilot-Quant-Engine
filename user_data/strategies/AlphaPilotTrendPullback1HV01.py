"""AlphaPilot Trend Pullback 1H V0.1 strategy.

This strategy is for research and backtesting only.
It is not approved for Dry-run or live trading.
It does not use real API keys.

本策略仅用于研究和回测。
不得用于 Dry-run 或实盘。
不得接真实 API Key。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
from pandas import DataFrame

try:
    from freqtrade.strategy import IStrategy, merge_informative_pair
except ModuleNotFoundError:  # Allows local static import without Freqtrade.
    class IStrategy:  # type: ignore[no-redef]
        pass

    def merge_informative_pair(  # type: ignore[no-redef]
        dataframe: DataFrame,
        informative: DataFrame,
        timeframe: str,
        informative_timeframe: str,
        ffill: bool = True,
    ) -> DataFrame:
        return dataframe


class AlphaPilotTrendPullback1HV01(IStrategy):
    """Long-only 1h trend pullback continuation research strategy."""

    INTERFACE_VERSION = 3

    strategy_id = "alpha_trend_pullback_1h_v01"
    strategy_version = "0.1-v13.4.8"
    strategy_name = "AlphaPilot Trend Pullback 1H V0.1"
    strategy_status = "research_backtest_only"

    timeframe = "1h"
    can_short = False
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
        "name": strategy_name,
        "status": strategy_status,
        "market": "OKX USDT swap",
        "direction": "long only",
        "timeframe": "1h",
        "higher_timeframe": "4h",
        "btc_filter_timeframes": ["1h", "4h"],
        "stoploss": -0.025,
        "take_profit": 0.05,
        "time_stop": "8h if not profitable",
        "momentum_exit": "profit-only MACD histogram weakness",
        "dry_run_approved": False,
        "live_trading_approved": False,
    }

    def informative_pairs(self) -> list[tuple[str, str]]:
        """Load pair 4h data plus BTC 1h/4h safety data."""
        pairs: list[str] = []
        if getattr(self, "dp", None):
            try:
                pairs = list(self.dp.current_whitelist())
            except Exception:
                pairs = []

        informative = {(pair, "4h") for pair in pairs}
        informative.add(("BTC/USDT:USDT", "1h"))
        informative.add(("BTC/USDT:USDT", "4h"))
        return sorted(informative)

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
        true_range = DataFrame(
            {
                "high_low": dataframe["high"] - dataframe["low"],
                "high_prev_close": (dataframe["high"] - previous_close).abs(),
                "low_prev_close": (dataframe["low"] - previous_close).abs(),
            }
        ).max(axis=1)
        dataframe["atr14"] = true_range.rolling(14, min_periods=14).mean()
        dataframe["atr_pct"] = dataframe["atr14"] / dataframe["close"].replace(0, np.nan)
        return dataframe

    def _merge_pair_4h_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        pair = metadata.get("pair")
        if not pair or not getattr(self, "dp", None):
            return self._mark_4h_missing(dataframe)

        try:
            informative = self.dp.get_pair_dataframe(pair=pair, timeframe="4h")
        except Exception:
            informative = DataFrame()

        if informative.empty or "date" not in informative.columns:
            return self._mark_4h_missing(dataframe)

        informative = informative.copy()
        informative["ema20"] = informative["close"].ewm(span=20, adjust=False).mean()
        informative["ema50"] = informative["close"].ewm(span=50, adjust=False).mean()
        informative["ema200"] = informative["close"].ewm(span=200, adjust=False).mean()
        informative = informative[["date", "close", "ema20", "ema50", "ema200"]]
        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, "4h", ffill=True)

        for column in ("close_4h", "ema20_4h", "ema50_4h", "ema200_4h"):
            if column not in dataframe.columns:
                dataframe[column] = np.nan
        dataframe["trend_4h_data_missing"] = dataframe[["close_4h", "ema20_4h", "ema50_4h", "ema200_4h"]].isna().any(axis=1)
        return dataframe

    @staticmethod
    def _mark_4h_missing(dataframe: DataFrame) -> DataFrame:
        for column in ("close_4h", "ema20_4h", "ema50_4h", "ema200_4h"):
            dataframe[column] = np.nan
        dataframe["trend_4h_data_missing"] = True
        return dataframe

    def _merge_btc_1h_safety(self, dataframe: DataFrame) -> DataFrame:
        if not getattr(self, "dp", None):
            return self._mark_btc_1h_missing(dataframe)

        try:
            btc = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe="1h")
        except Exception:
            btc = DataFrame()

        if btc.empty or "date" not in btc.columns:
            return self._mark_btc_1h_missing(dataframe)

        btc = btc.copy()
        ema12 = btc["close"].ewm(span=12, adjust=False).mean()
        ema26 = btc["close"].ewm(span=26, adjust=False).mean()
        btc["btc_macd"] = ema12 - ema26
        btc["btc_macd_signal"] = btc["btc_macd"].ewm(span=9, adjust=False).mean()
        btc["btc_macd_histogram_1h"] = btc["btc_macd"] - btc["btc_macd_signal"]
        btc["btc_close_1h"] = btc["close"]
        btc["btc_1h_return_3"] = (btc["close"] / btc["close"].shift(3)) - 1
        btc_view = btc[["date", "btc_close_1h", "btc_1h_return_3", "btc_macd_histogram_1h"]]
        dataframe = dataframe.merge(btc_view, on="date", how="left")

        dataframe["btc_1h_data_missing"] = dataframe[["btc_close_1h", "btc_1h_return_3", "btc_macd_histogram_1h"]].isna().any(axis=1)
        return dataframe

    @staticmethod
    def _mark_btc_1h_missing(dataframe: DataFrame) -> DataFrame:
        dataframe["btc_close_1h"] = np.nan
        dataframe["btc_1h_return_3"] = np.nan
        dataframe["btc_macd_histogram_1h"] = np.nan
        dataframe["btc_1h_data_missing"] = True
        return dataframe

    def _merge_btc_4h_safety(self, dataframe: DataFrame) -> DataFrame:
        if not getattr(self, "dp", None):
            return self._mark_btc_4h_missing(dataframe)

        try:
            btc = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe="4h")
        except Exception:
            btc = DataFrame()

        if btc.empty or "date" not in btc.columns:
            return self._mark_btc_4h_missing(dataframe)

        btc = btc.copy()
        btc["btc_close"] = btc["close"]
        btc["btc_ema200"] = btc["close"].ewm(span=200, adjust=False).mean()
        btc_view = btc[["date", "btc_close", "btc_ema200"]]
        dataframe = merge_informative_pair(dataframe, btc_view, self.timeframe, "4h", ffill=True)

        for column in ("btc_close_4h", "btc_ema200_4h"):
            if column not in dataframe.columns:
                dataframe[column] = np.nan
        dataframe["btc_4h_data_missing"] = dataframe[["btc_close_4h", "btc_ema200_4h"]].isna().any(axis=1)
        return dataframe

    @staticmethod
    def _mark_btc_4h_missing(dataframe: DataFrame) -> DataFrame:
        dataframe["btc_close_4h"] = np.nan
        dataframe["btc_ema200_4h"] = np.nan
        dataframe["btc_4h_data_missing"] = True
        return dataframe

    @staticmethod
    def _entry_conditions(dataframe: DataFrame) -> Any:
        return (
            dataframe["ap_v03_audit_pass_4h_trend"]
            & dataframe["ap_v03_audit_pass_btc_safety"]
            & dataframe["ap_v03_audit_pass_pullback_location"]
            & dataframe["ap_v03_audit_pass_reclaim_confirmation"]
            & dataframe["ap_v03_audit_pass_volume_quality"]
            & dataframe["ap_v03_audit_pass_no_chase"]
            & (dataframe["volume"] > 0)
            & ~dataframe["ap_v03_audit_data_missing"]
        )

    @staticmethod
    def _add_audit_columns(dataframe: DataFrame) -> DataFrame:
        required_columns = [
            "close",
            "ema20",
            "ema50",
            "ema200",
            "rsi14",
            "macd_histogram",
            "volume_ratio",
            "atr_pct",
            "close_4h",
            "ema20_4h",
            "ema50_4h",
            "ema200_4h",
            "btc_close_1h",
            "btc_1h_return_3",
            "btc_macd_histogram_1h",
            "btc_close_4h",
            "btc_ema200_4h",
        ]
        dataframe["ap_v03_audit_data_missing"] = dataframe[required_columns].isna().any(axis=1)
        dataframe["ap_v03_audit_pass_4h_trend"] = dataframe["trend_4h_ok"].fillna(False)
        dataframe["ap_v03_audit_pass_btc_safety"] = dataframe["btc_market_safe"].fillna(False)
        dataframe["ap_v03_audit_pass_pullback_location"] = dataframe["pullback_location_ok"].fillna(False)
        dataframe["ap_v03_audit_pass_reclaim_confirmation"] = dataframe["reclaim_confirmation_ok"].fillna(False)
        dataframe["ap_v03_audit_pass_volume_quality"] = dataframe["volume_quality_ok"].fillna(False)
        dataframe["ap_v03_audit_pass_no_chase"] = dataframe["no_chase_ok"].fillna(False)
        dataframe["ap_v03_audit_final_entry"] = AlphaPilotTrendPullback1HV01._entry_conditions(dataframe)

        dataframe["ap_v03_audit_close"] = dataframe["close"]
        dataframe["ap_v03_audit_ema20"] = dataframe["ema20"]
        dataframe["ap_v03_audit_ema50"] = dataframe["ema50"]
        dataframe["ap_v03_audit_ema200"] = dataframe["ema200"]
        dataframe["ap_v03_audit_rsi14"] = dataframe["rsi14"]
        dataframe["ap_v03_audit_macd_hist"] = dataframe["macd_histogram"]
        dataframe["ap_v03_audit_volume_ratio"] = dataframe["volume_ratio"]
        dataframe["ap_v03_audit_atr_pct"] = dataframe["atr_pct"]
        dataframe["ap_v03_audit_4h_close"] = dataframe["close_4h"]
        dataframe["ap_v03_audit_4h_ema200"] = dataframe["ema200_4h"]
        dataframe["ap_v03_audit_btc_1h_return_3"] = dataframe["btc_1h_return_3"]
        dataframe["ap_v03_audit_btc_4h_close"] = dataframe["btc_close_4h"]
        dataframe["ap_v03_audit_btc_4h_ema200"] = dataframe["btc_ema200_4h"]

        dataframe["ap_v03_audit_skip_reason"] = np.select(
            [
                dataframe["ap_v03_audit_final_entry"],
                dataframe["ap_v03_audit_data_missing"],
                ~dataframe["ap_v03_audit_pass_4h_trend"],
                ~dataframe["ap_v03_audit_pass_btc_safety"],
                ~dataframe["ap_v03_audit_pass_pullback_location"],
                ~dataframe["ap_v03_audit_pass_reclaim_confirmation"],
                ~dataframe["ap_v03_audit_pass_volume_quality"],
                ~dataframe["ap_v03_audit_pass_no_chase"],
            ],
            [
                "entry_signal_passed",
                "data_missing",
                "weak_4h_trend",
                "btc_not_safe",
                "not_in_pullback_zone",
                "reclaim_not_confirmed",
                "volume_quality_low",
                "price_too_extended",
            ],
            default="unknown",
        )
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self._add_core_indicators(dataframe)
        dataframe = self._merge_pair_4h_trend(dataframe, metadata)
        dataframe = self._merge_btc_1h_safety(dataframe)
        dataframe = self._merge_btc_4h_safety(dataframe)

        dataframe["trend_4h_ok"] = (
            dataframe["close_4h"].notna()
            & dataframe["ema200_4h"].notna()
            & dataframe["ema20_4h"].notna()
            & dataframe["ema50_4h"].notna()
            & (dataframe["close_4h"] > dataframe["ema200_4h"])
            & (dataframe["ema20_4h"] >= dataframe["ema50_4h"])
            & (dataframe["ema20_4h"] >= dataframe["ema20_4h"].shift(1))
        )
        btc_hist_worsening_two = (
            (dataframe["btc_macd_histogram_1h"] < dataframe["btc_macd_histogram_1h"].shift(1))
            & (dataframe["btc_macd_histogram_1h"].shift(1) < dataframe["btc_macd_histogram_1h"].shift(2))
        )
        dataframe["btc_market_safe"] = (
            dataframe["btc_1h_return_3"].notna()
            & (dataframe["btc_1h_return_3"] > -0.015)
            & dataframe["btc_close_4h"].notna()
            & dataframe["btc_ema200_4h"].notna()
            & (dataframe["btc_close_4h"] >= dataframe["btc_ema200_4h"])
            & ~btc_hist_worsening_two.fillna(True)
        )
        dataframe["pullback_location_ok"] = (
            (dataframe["close"] >= dataframe["ema50"])
            & (dataframe["close"] >= dataframe["ema20"] * 0.985)
            & (dataframe["close"] <= dataframe["ema20"] * 1.015)
        )
        dataframe["reclaim_confirmation_ok"] = (
            (dataframe["close"] > dataframe["ema20"])
            & (dataframe["macd_histogram"] > dataframe["macd_histogram"].shift(1))
        )
        dataframe["volume_quality_ok"] = dataframe["volume_ratio"] >= 1.2
        dataframe["no_chase_ok"] = (
            (dataframe["close"] <= dataframe["ema20"] * 1.02)
            & (dataframe["rsi14"] <= 65)
            & (dataframe["atr_pct"] <= 0.08)
        )
        dataframe = self._add_audit_columns(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = ""

        entry_conditions = self._entry_conditions(dataframe)
        dataframe.loc[entry_conditions, "enter_long"] = 1
        dataframe.loc[entry_conditions, "enter_tag"] = "trend_pullback_1h_v01"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_tag"] = ""
        return dataframe

    def _current_macd_weak_profit_exit(self, pair: str, current_time: datetime) -> bool:
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
        """Apply ExitProfileA time stop and profit-only MACD weakness exit."""
        open_date = getattr(trade, "open_date_utc", None)
        if open_date is None:
            return None

        age_hours = (current_time - open_date).total_seconds() / 3600
        if age_hours >= 8 and current_profit <= 0:
            return "time_stop_8h_not_profitable"
        if current_profit > 0 and self._current_macd_weak_profit_exit(pair, current_time):
            return "profitable_macd_weakness_exit"
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
        """Use the research leverage cap while respecting exchange max leverage."""
        return min(5.0, max_leverage)
