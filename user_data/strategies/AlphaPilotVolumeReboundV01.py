"""AlphaPilot Volume Rebound V0.1 strategy.

This strategy is for research backtesting only. It does not perform live
trading, does not read a real account, and does not create real orders.

V13.3 assumptions:
- Signals are evaluated on closed candles.
- Freqtrade backtests enter on the next candle according to its engine rules.
- The strategy uses vectorized rolling/shift logic and does not use iloc[-1]
  for historical signal generation.
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


class AlphaPilotVolumeReboundV01(IStrategy):
    """Volume rebound research strategy for baseline Freqtrade backtests."""

    INTERFACE_VERSION = 3

    strategy_id = "alpha_volume_rebound_v01"
    strategy_version = "0.1-v13.3"
    timeframe = "15m"
    can_short = False

    stoploss = -0.03
    minimal_roi = {
        "0": 0.03,
    }
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count = 260
    process_only_new_candles = True

    alphapilot_parameters = {
        "market": "OKX USDT swap",
        "direction": "long only",
        "timeframe": "15m",
        "fixed_stop_loss": -0.03,
        "take_profit": 0.03,
        "leverage": 5,
        "risk_per_trade": 0.01,
        "fee_rate_one_way": 0.0005,
        "slippage_rate_one_way": 0.0005,
        "btc_crash_filter": "BTC latest three 15m candles cumulative return <= -1% blocks new entries",
        "trend_filter": "4h close must be >= EMA200 * 0.98",
        "universe": "fixed Top 30 OKX USDT swap pairs",
    }

    def informative_pairs(self) -> list[tuple[str, str]]:
        """Load current pair 4h data and BTC 15m data for research filters."""
        pairs: list[str] = []
        if getattr(self, "dp", None):
            try:
                pairs = list(self.dp.current_whitelist())
            except Exception:
                pairs = []

        informative = {(pair, "4h") for pair in pairs}
        informative.add(("BTC/USDT:USDT", self.timeframe))
        return sorted(informative)

    @staticmethod
    def _add_core_indicators(dataframe: DataFrame) -> DataFrame:
        dataframe["ema20"] = dataframe["close"].ewm(span=20, adjust=False).mean()
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

    def _merge_4h_trend(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        pair = metadata.get("pair")
        if not pair or not getattr(self, "dp", None):
            dataframe["close_4h"] = np.nan
            dataframe["ema20_4h"] = np.nan
            dataframe["ema200_4h"] = np.nan
            dataframe["trend_4h_data_missing"] = True
            return dataframe

        try:
            informative = self.dp.get_pair_dataframe(pair=pair, timeframe="4h")
        except Exception:
            informative = DataFrame()

        if informative.empty:
            dataframe["close_4h"] = np.nan
            dataframe["ema20_4h"] = np.nan
            dataframe["ema200_4h"] = np.nan
            dataframe["trend_4h_data_missing"] = True
            return dataframe

        informative = informative.copy()
        informative["ema20"] = informative["close"].ewm(span=20, adjust=False).mean()
        informative["ema200"] = informative["close"].ewm(span=200, adjust=False).mean()
        informative = informative[["date", "close", "ema20", "ema200"]]
        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, "4h", ffill=True)

        for column in ("close_4h", "ema20_4h", "ema200_4h"):
            if column not in dataframe.columns:
                dataframe[column] = np.nan

        dataframe["trend_4h_data_missing"] = dataframe[["close_4h", "ema200_4h"]].isna().any(axis=1)
        return dataframe

    def _merge_btc_filter(self, dataframe: DataFrame) -> DataFrame:
        if not getattr(self, "dp", None):
            dataframe["btc_close_15m"] = np.nan
            dataframe["btc_3_candle_return_15m"] = np.nan
            dataframe["btc_data_missing"] = True
            dataframe["btc_crash_filter_blocked"] = True
            return dataframe

        try:
            btc = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe=self.timeframe)
        except Exception:
            btc = DataFrame()

        if btc.empty or "date" not in btc.columns:
            dataframe["btc_close_15m"] = np.nan
            dataframe["btc_3_candle_return_15m"] = np.nan
            dataframe["btc_data_missing"] = True
            dataframe["btc_crash_filter_blocked"] = True
            return dataframe

        btc = btc.copy()
        btc["btc_close_15m"] = btc["close"]
        btc["btc_3_candle_return_15m"] = (btc["close"] / btc["close"].shift(3)) - 1
        btc_view = btc[["date", "btc_close_15m", "btc_3_candle_return_15m"]]
        dataframe = dataframe.merge(btc_view, on="date", how="left")

        dataframe["btc_data_missing"] = dataframe["btc_3_candle_return_15m"].isna()
        dataframe["btc_crash_filter_blocked"] = (
            dataframe["btc_data_missing"] | (dataframe["btc_3_candle_return_15m"] <= -0.01)
        )
        return dataframe

    @staticmethod
    def _entry_conditions(dataframe: DataFrame) -> Any:
        return (
            ~dataframe["btc_crash_filter_blocked"]
            & dataframe["trend_4h_ok"]
            & dataframe["rsi_ok"]
            & dataframe["volume_rebound_ok"]
            & dataframe["macd_improving"]
            & dataframe["near_ema20_ok"]
            & dataframe["pullback_zone_ok"]
            & ~dataframe["skip_data_missing"]
        )

    @staticmethod
    def _add_audit_columns(dataframe: DataFrame) -> DataFrame:
        dataframe["ap_audit_data_ready"] = ~dataframe["skip_data_missing"]
        dataframe["ap_audit_base_candidate"] = dataframe["ap_audit_data_ready"]
        dataframe["ap_audit_pass_btc_crash_filter"] = ~dataframe["btc_crash_filter_blocked"]
        dataframe["ap_audit_pass_4h_trend_filter"] = dataframe["trend_4h_ok"]
        dataframe["ap_audit_pass_rsi_filter"] = dataframe["rsi_ok"]
        dataframe["ap_audit_pass_volume_filter"] = dataframe["volume_rebound_ok"]
        dataframe["ap_audit_pass_macd_filter"] = dataframe["macd_improving"]
        dataframe["ap_audit_pass_ema20_reclaim_filter"] = dataframe["near_ema20_ok"]
        dataframe["ap_audit_pass_no_chase_filter"] = dataframe["pullback_zone_ok"]
        dataframe["ap_audit_final_entry"] = AlphaPilotVolumeReboundV01._entry_conditions(dataframe)

        dataframe["ap_audit_close"] = dataframe["close"]
        dataframe["ap_audit_volume"] = dataframe["volume"]
        dataframe["ap_audit_volume_ratio"] = dataframe["volume_ratio"]
        dataframe["ap_audit_rsi14"] = dataframe["rsi14"]
        dataframe["ap_audit_macd_hist"] = dataframe["macd_histogram"]
        dataframe["ap_audit_macd_hist_prev"] = dataframe["macd_histogram"].shift(1)
        dataframe["ap_audit_ema20"] = dataframe["ema20"]
        dataframe["ap_audit_ema200"] = dataframe["ema200"]
        dataframe["ap_audit_bb_middle"] = dataframe["bb_middle"]
        dataframe["ap_audit_bb_lower"] = dataframe["bb_lower"]
        dataframe["ap_audit_btc_3_candle_return"] = dataframe["btc_3_candle_return_15m"]
        dataframe["ap_audit_4h_close"] = dataframe["close_4h"]
        dataframe["ap_audit_4h_ema200"] = dataframe["ema200_4h"]

        dataframe["ap_audit_skip_reason"] = np.select(
            [
                dataframe["ap_audit_final_entry"],
                ~dataframe["ap_audit_data_ready"],
                ~dataframe["ap_audit_pass_btc_crash_filter"],
                ~dataframe["ap_audit_pass_4h_trend_filter"],
                ~dataframe["ap_audit_pass_rsi_filter"],
                ~dataframe["ap_audit_pass_volume_filter"],
                ~dataframe["ap_audit_pass_macd_filter"],
                ~dataframe["ap_audit_pass_ema20_reclaim_filter"],
                ~dataframe["ap_audit_pass_no_chase_filter"],
            ],
            [
                "entry_signal_passed",
                "data_missing",
                "btc_crash_filter",
                "weak_4h_trend",
                "rsi_out_of_range",
                "volume_ratio_too_low",
                "macd_not_improving",
                "ema20_reclaim_failed",
                "price_too_extended",
            ],
            default="unknown",
        )

        audit_filters = [
            ("btc_crash_filter", "ap_audit_pass_btc_crash_filter"),
            ("weak_4h_trend", "ap_audit_pass_4h_trend_filter"),
            ("rsi_out_of_range", "ap_audit_pass_rsi_filter"),
            ("volume_ratio_too_low", "ap_audit_pass_volume_filter"),
            ("macd_not_improving", "ap_audit_pass_macd_filter"),
            ("ema20_reclaim_failed", "ap_audit_pass_ema20_reclaim_filter"),
            ("price_too_extended", "ap_audit_pass_no_chase_filter"),
        ]

        def failed_filters(row: Any) -> str:
            if not bool(row["ap_audit_data_ready"]):
                return "data_missing"
            failed = [reason for reason, column in audit_filters if not bool(row[column])]
            return "|".join(failed) if failed else "none"

        dataframe["ap_audit_failed_filters"] = dataframe.apply(failed_filters, axis=1)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self._add_core_indicators(dataframe)
        dataframe = self._merge_4h_trend(dataframe, metadata)
        dataframe = self._merge_btc_filter(dataframe)

        dataframe["trend_4h_ok"] = (
            dataframe["close_4h"].notna()
            & dataframe["ema200_4h"].notna()
            & (dataframe["close_4h"] >= dataframe["ema200_4h"] * 0.98)
        )
        dataframe["rsi_ok"] = dataframe["rsi14"].between(30, 55, inclusive="both")
        dataframe["volume_rebound_ok"] = dataframe["volume_ratio"] >= 1.5
        dataframe["macd_improving"] = dataframe["macd_histogram"] > dataframe["macd_histogram"].shift(1)
        dataframe["near_ema20_ok"] = dataframe["close"] >= dataframe["ema20"] * 0.995
        dataframe["pullback_zone_ok"] = dataframe["close"] <= dataframe["bb_middle"] * 1.01

        dataframe["skip_btc_crash_filter"] = dataframe["btc_crash_filter_blocked"]
        dataframe["skip_weak_4h_trend"] = ~dataframe["trend_4h_ok"]
        dataframe["skip_rsi_out_of_range"] = ~dataframe["rsi_ok"]
        dataframe["skip_volume_ratio_too_low"] = ~dataframe["volume_rebound_ok"]
        dataframe["skip_macd_not_improving"] = ~dataframe["macd_improving"]
        dataframe["skip_price_too_extended"] = ~dataframe["pullback_zone_ok"]
        dataframe["skip_data_missing"] = dataframe[
            ["btc_data_missing", "trend_4h_data_missing", "volume_ratio", "bb_middle", "ema20", "rsi14"]
        ].isna().any(axis=1) | dataframe[["btc_data_missing", "trend_4h_data_missing"]].any(axis=1)
        dataframe = self._add_audit_columns(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = ""

        entry_conditions = self._entry_conditions(dataframe)

        dataframe.loc[entry_conditions, "enter_long"] = 1
        dataframe.loc[entry_conditions, "enter_tag"] = "volume_rebound_v0_1"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_tag"] = ""

        macd_weak_two_candles = (
            (dataframe["macd_histogram"] < dataframe["macd_histogram"].shift(1))
            & (dataframe["macd_histogram"].shift(1) < dataframe["macd_histogram"].shift(2))
        )
        dataframe.loc[macd_weak_two_candles, "exit_long"] = 1
        dataframe.loc[macd_weak_two_candles, "exit_tag"] = "macd_histogram_two_candle_weakness"
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade: Any,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs: Any,
    ) -> str | None:
        """Exit after 12 candles if the paper backtest trade is still not profitable."""
        open_date = getattr(trade, "open_date_utc", None)
        if open_date is None:
            return None

        age_minutes = (current_time - open_date).total_seconds() / 60
        if age_minutes >= 12 * 15 and current_profit <= 0:
            return "time_stop_12_candles_no_profit"
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
        """Use the V0.1 research leverage cap while respecting exchange max leverage."""
        return min(5.0, max_leverage)
