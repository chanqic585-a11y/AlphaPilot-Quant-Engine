"""AlphaPilot Volume Rebound V0.1 strategy placeholder.

This strategy is for research and backtest preparation only. It is not live
trading advice. AlphaPilot V13.2 does not allow live trading.
"""

from __future__ import annotations

from pandas import DataFrame

from freqtrade.strategy import IStrategy


class AlphaPilotVolumeReboundV01(IStrategy):
    """Skeleton strategy for V13.3 volume rebound backtest work."""

    strategy_id = "alpha_volume_rebound_v01"
    strategy_version = "0.1-skeleton"
    timeframe = "15m"
    can_short = False
    stoploss = -0.03
    minimal_roi = {
        "0": 0.03,
    }

    # V0.1 consensus parameters for documentation and future risk integration.
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
        "btc_crash_filter": "BTC latest three 15m candles cumulative return <= -1% blocks new signals",
        "universe": "fixed Top 30 OKX USDT swap pairs",
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Add indicator placeholders for V13.3 signal development."""
        dataframe["ema20"] = dataframe["close"].ewm(span=20, adjust=False).mean()
        dataframe["ema200"] = dataframe["close"].ewm(span=200, adjust=False).mean()

        delta = dataframe["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-12)
        dataframe["rsi14"] = 100 - (100 / (1 + rs))

        ema12 = dataframe["close"].ewm(span=12, adjust=False).mean()
        ema26 = dataframe["close"].ewm(span=26, adjust=False).mean()
        dataframe["macd"] = ema12 - ema26
        dataframe["macd_signal"] = dataframe["macd"].ewm(span=9, adjust=False).mean()
        dataframe["macd_histogram"] = dataframe["macd"] - dataframe["macd_signal"]

        dataframe["volume_mean_20"] = dataframe["volume"].rolling(20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_mean_20"].replace(0, 1e-12)

        middle = dataframe["close"].rolling(20).mean()
        std = dataframe["close"].rolling(20).std()
        dataframe["bb_middle"] = middle
        dataframe["bb_upper"] = middle + std * 2
        dataframe["bb_lower"] = middle - std * 2

        dataframe["btc_crash_filter_blocked"] = False
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """V13.2 placeholder entry logic.

        V13.3 should implement:
        1. BTC is not in a short-term crash filter.
        2. 4h trend is not strongly bearish.
        3. RSI14 is between 30 and 55.
        4. volume_ratio >= 1.5.
        5. MACD histogram is improving.
        6. close >= EMA20 * 0.995.
        7. price is in a pullback zone rather than chasing a high.
        """
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = "v13_2_placeholder_no_live_signal"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """V13.2 placeholder exit logic.

        V13.3 should implement MACD weakness and time-stop research exits.
        Fixed stop loss and +3% ROI are already recorded above for backtest work.
        """
        dataframe["exit_long"] = 0
        dataframe["exit_tag"] = "v13_2_placeholder_exit"
        return dataframe
