"""Research-only Freqtrade translation of frozen Advisory-R candidate S01."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from pandas import DataFrame

from alphapilot.formal_validation.s01_freqtrade_translation import (
    s01_entry_mask,
    s01_indicator_frame,
    s01_structure_exit_mask,
)

try:
    from freqtrade.strategy import IStrategy, stoploss_from_absolute
except ModuleNotFoundError:  # Static tests intentionally run without Freqtrade.
    class IStrategy:  # type: ignore[no-redef]
        pass

    def stoploss_from_absolute(  # type: ignore[no-redef]
        stop_rate: float,
        current_rate: float,
        *,
        is_short: bool = False,
        leverage: float = 1.0,
    ) -> float:
        del is_short
        return max(-0.99, (stop_rate / current_rate - 1.0) * leverage)


class AlphaPilotS01BearRecovery4H(IStrategy):
    """Exact entry semantics plus auditable exit translation for S01."""

    INTERFACE_VERSION = 3

    candidate_id = "s01_bear_idiosyncratic_selloff_recovery_4h"
    strategy_status = "formal_research_only"
    dry_run_approved = False
    live_trading_approved = False
    translation_parity_status = "pending_formal_dual_engine_audit"

    timeframe = "4h"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 240
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    position_adjustment_enable = True
    use_custom_stoploss = True
    stoploss = -0.20
    minimal_roi: dict[str, float] = {}

    feature_definition = {
        "marketRegime": "btc_close_below_ema_200",
        "residualWindow": 30,
        "residualZMaximum": -2.25,
        "recoveryBars": 2,
    }
    entry_definition = {"kind": "residual_reclaim", "minimumRecoveryZ": 0.35}
    initial_stop_atr_multiple = 1.6
    partial_at_r = 0.7
    partial_fraction = 0.4
    maximum_hold_bars = 24

    def informative_pairs(self) -> list[tuple[str, str]]:
        pairs: list[str] = []
        if getattr(self, "dp", None):
            try:
                pairs = list(self.dp.current_whitelist())
            except Exception:
                pairs = []
        pairs.append("BTC/USDT:USDT")
        return sorted({(pair, "4h") for pair in pairs})

    def _load_market_context(
        self, dataframe: DataFrame
    ) -> tuple[pd.Series, pd.Series]:
        dates = pd.DatetimeIndex(dataframe["date"])
        if not getattr(self, "dp", None):
            missing = pd.Series(np.nan, index=dates, dtype="float64")
            return missing, missing

        try:
            pairs = sorted(set(self.dp.current_whitelist()))
        except Exception:
            pairs = []
        closes: dict[str, pd.Series] = {}
        for pair in pairs:
            try:
                frame = self.dp.get_pair_dataframe(pair=pair, timeframe="4h")
            except Exception:
                continue
            if frame.empty or "date" not in frame.columns:
                continue
            closes[pair] = frame.set_index("date")["close"]
        market_close = (
            pd.concat(closes, axis=1).sort_index().median(axis=1, skipna=True)
            if closes
            else pd.Series(np.nan, index=dates, dtype="float64")
        )
        btc_close = closes.get(
            "BTC/USDT:USDT", pd.Series(np.nan, index=dates, dtype="float64")
        )
        return btc_close, market_close

    @staticmethod
    def _atr14(dataframe: DataFrame) -> pd.Series:
        previous = dataframe["close"].shift(1)
        true_range = pd.concat(
            [
                dataframe["high"] - dataframe["low"],
                (dataframe["high"] - previous).abs(),
                (dataframe["low"] - previous).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return true_range.rolling(14, min_periods=14).mean()

    def populate_indicators(
        self, dataframe: DataFrame, metadata: dict[str, Any]
    ) -> DataFrame:
        del metadata
        dataframe = dataframe.copy()
        btc_close, market_close = self._load_market_context(dataframe)
        indicators = s01_indicator_frame(
            frame=dataframe,
            btc_close=btc_close,
            market_close=market_close,
            feature_definition=self.feature_definition,
        )
        for column in indicators:
            dataframe[column] = indicators[column]
        dataframe["s01_entry_signal"] = s01_entry_mask(
            frame=dataframe,
            btc_close=btc_close,
            market_close=market_close,
            feature_definition=self.feature_definition,
            entry_definition=self.entry_definition,
        ).astype(int)
        dataframe["s01_structure_exit"] = s01_structure_exit_mask(indicators).astype(int)
        dataframe["s01_atr14"] = self._atr14(dataframe)
        dataframe["s01_context_missing"] = dataframe[
            ["s01_btc_close", "s01_btc_ema_200", "s01_residual_z"]
        ].isna().any(axis=1)
        return dataframe

    def populate_entry_trend(
        self, dataframe: DataFrame, metadata: dict[str, Any]
    ) -> DataFrame:
        del metadata
        dataframe.loc[
            dataframe["s01_entry_signal"].eq(1)
            & ~dataframe["s01_context_missing"]
            & dataframe["volume"].gt(0),
            ["enter_long", "enter_tag"],
        ] = (1, "s01_residual_reclaim")
        return dataframe

    def populate_exit_trend(
        self, dataframe: DataFrame, metadata: dict[str, Any]
    ) -> DataFrame:
        del metadata
        dataframe.loc[
            dataframe["s01_structure_exit"].eq(1),
            ["exit_long", "exit_tag"],
        ] = (1, "s01_residual_neutral")
        return dataframe

    def _entry_atr(self, pair: str, trade: Any) -> float | None:
        if not getattr(self, "dp", None):
            return None
        try:
            analyzed, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        except Exception:
            return None
        if analyzed.empty or "s01_atr14" not in analyzed.columns:
            return None
        eligible = analyzed.loc[analyzed["date"] <= trade.open_date_utc]
        if eligible.empty:
            return None
        value = float(eligible.iloc[-1]["s01_atr14"])
        return value if np.isfinite(value) and value > 0 else None

    def custom_stoploss(
        self,
        pair: str,
        trade: Any,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs: Any,
    ) -> float:
        del current_time, current_profit, after_fill, kwargs
        atr = self._entry_atr(pair, trade)
        if atr is None:
            return self.stoploss
        stop_price = float(trade.open_rate) - self.initial_stop_atr_multiple * atr
        return stoploss_from_absolute(
            stop_price,
            current_rate,
            is_short=False,
            leverage=float(getattr(trade, "leverage", 1.0) or 1.0),
        )

    def adjust_trade_position(
        self,
        trade: Any,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: float | None,
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs: Any,
    ) -> tuple[float, str] | None:
        del (
            current_time,
            current_profit,
            min_stake,
            max_stake,
            current_entry_rate,
            current_exit_rate,
            current_entry_profit,
            current_exit_profit,
            kwargs,
        )
        if int(getattr(trade, "nr_of_successful_exits", 0) or 0) > 0:
            return None
        atr = self._entry_atr(str(trade.pair), trade)
        if atr is None:
            return None
        risk_distance = self.initial_stop_atr_multiple * atr
        if current_rate < float(trade.open_rate) + self.partial_at_r * risk_distance:
            return None
        return -(float(trade.stake_amount) * self.partial_fraction), "s01_partial_0_7r"

    def custom_exit(
        self,
        pair: str,
        trade: Any,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs: Any,
    ) -> str | None:
        del pair, current_rate, current_profit, kwargs
        maximum_duration = timedelta(hours=self.maximum_hold_bars * 4)
        if current_time - trade.open_date_utc >= maximum_duration:
            return "s01_maximum_hold_24_bars"
        return None
