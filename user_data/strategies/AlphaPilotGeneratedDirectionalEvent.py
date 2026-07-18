"""Candidate-neutral generated directional-event Freqtrade runtime shell."""

from __future__ import annotations

from datetime import datetime

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy
from pandas import DataFrame


class AlphaPilotGeneratedDirectionalEvent(IStrategy):
    """Runtime-loaded shell; frozen candidate logic is supplied by its adapter."""

    INTERFACE_VERSION = 3
    timeframe = "4h"
    can_short = True
    minimal_roi = {"0": 100.0}
    stoploss = -0.99
    position_adjustment_enable = False
    process_only_new_candles = True
    startup_candle_count = 100

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        del metadata
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        del metadata
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        del metadata
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs: object,
    ) -> float:
        del pair, trade, current_time, current_rate, current_profit, after_fill, kwargs
        return self.stoploss

    def adjust_trade_position(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        return None
