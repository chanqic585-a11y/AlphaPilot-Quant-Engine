"""AlphaPilot Dynamic Regime V0.1 strategy.

This strategy is for research backtesting only. It is not approved for Dry-run
or live trading. It does not use real API keys, call exchange private APIs,
read accounts, read positions, create orders, or auto trade.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from pandas import DataFrame, Series

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


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def bucket_id(parts: list[str]) -> str:
    return "_".join(part.replace("/", "_").replace(":", "_") for part in parts)


def liquidity_bucket(quote_volume_24h: Any) -> str:
    value = safe_float(quote_volume_24h)
    if value is None or value <= 0:
        return "unavailable"
    if value >= 1_000_000_000:
        return "high"
    if value >= 100_000_000:
        return "medium"
    return "low"


def volatility_bucket(atr_pct: Any) -> str:
    value = safe_float(atr_pct)
    if value is None or value < 0:
        return "unavailable"
    if value < 0.02:
        return "low"
    if value < 0.05:
        return "medium"
    if value < 0.08:
        return "high"
    return "extreme"


def rsi_bucket(rsi14: Any) -> str:
    value = safe_float(rsi14)
    if value is None:
        return "unavailable"
    if value < 30:
        return "below30"
    if value < 45:
        return "30-45"
    if value < 55:
        return "45-55"
    if value < 65:
        return "55-65"
    return "above65"


def ema_distance_bucket(close: Any, ema20: Any) -> str:
    price = safe_float(close)
    ema = safe_float(ema20)
    if price is None or price <= 0 or ema is None:
        return "unavailable"
    distance = (price - ema) / price
    if distance < -0.005:
        return "below_ema20"
    if abs(distance) <= 0.01:
        return "near_ema20"
    if distance > 0.03:
        return "extended_above_ema20"
    return "above_ema20"


def bollinger_position_bucket(close: Any, lower: Any, middle: Any, upper: Any) -> str:
    price = safe_float(close)
    low = safe_float(lower)
    mid = safe_float(middle)
    high = safe_float(upper)
    if price is None or low is None or mid is None or high is None or high <= low:
        return "unavailable"
    if price < low or price > high:
        return "outside"
    if price <= mid:
        return "lower"
    upper_mid = mid + ((high - mid) * 0.5)
    if price >= upper_mid:
        return "upper"
    return "middle"


def regime_candidate(close: Any, ema20: Any, ema50: Any, ema200: Any, rsi14: Any, atr_pct: Any, btc: str) -> str:
    price = safe_float(close)
    e20 = safe_float(ema20)
    e50 = safe_float(ema50)
    e200 = safe_float(ema200)
    rsi = safe_float(rsi14)
    atr = safe_float(atr_pct)
    if price is None or e20 is None or e50 is None or e200 is None or rsi is None:
        return "unknown"
    if btc == "crash" or (atr is not None and atr >= 0.08):
        return "avoid"
    if price > e200 and e20 > e50 and rsi >= 55:
        return "trend"
    if rsi <= 45 or price < e20:
        return "mean_reversion"
    if price < e200 and e20 < e50:
        return "avoid"
    return "unknown"


def get_pairs_for_timestamp(snapshots: list[dict[str, Any]], timestamp_iso: str) -> list[str]:
    target_date = timestamp_iso[:10]
    candidates = [snapshot for snapshot in snapshots if str(snapshot.get("snapshotDate", "")) <= target_date]
    if not candidates:
        return []
    latest = sorted(candidates, key=lambda item: str(item.get("snapshotDate")))[-1]
    return [str(pair) for pair in latest.get("selectedPairs", [])]


class AlphaPilotDynamicRegimeV01(IStrategy):
    """Dynamic universe + regime router research strategy."""

    INTERFACE_VERSION = 3

    strategy_id = "alpha_dynamic_regime_v01"
    strategy_version = "0.1-v13.4.15"
    strategy_name = "AlphaPilot Dynamic Regime V0.1"
    strategy_status = "research_backtest_only"

    timeframe = "1h"
    can_short = False
    stoploss = -0.025
    minimal_roi = {"0": 0.04}

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count = 260
    process_only_new_candles = True

    universe_snapshots_path = Path("reports/v13_4_13_dynamic_universe_snapshots.json")
    probability_score_table_path = Path("reports/v13_4_14_probability_score_table.json")
    probability_min_samples = 50
    allow_liquidity_gate_fallback_for_backtest = True

    _universe_snapshots_cache: list[dict[str, Any]] | None = None
    _probability_rows_cache: dict[str, dict[str, Any]] | None = None

    alphapilot_parameters = {
        "strategyId": strategy_id,
        "name": strategy_name,
        "status": strategy_status,
        "market": "OKX USDT swap",
        "direction": "long only",
        "timeframe": "1h",
        "higher_timeframe": "4h",
        "btc_filter_timeframes": ["1h", "4h"],
        "dynamic_universe_source": str(universe_snapshots_path),
        "probability_score_source": str(probability_score_table_path),
        "probability_min_samples": probability_min_samples,
        "liquidity_gate_fallback": "allowed for backtest research only; not a real liquidity approval",
        "dry_run_approved": False,
        "live_trading_approved": False,
    }

    def informative_pairs(self) -> list[tuple[str, str]]:
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
    def _read_json_list(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return payload if isinstance(payload, list) else []

    @classmethod
    def _universe_snapshots(cls) -> list[dict[str, Any]]:
        if cls._universe_snapshots_cache is None:
            cls._universe_snapshots_cache = cls._read_json_list(cls.universe_snapshots_path)
        return cls._universe_snapshots_cache

    @classmethod
    def _probability_rows(cls) -> dict[str, dict[str, Any]]:
        if cls._probability_rows_cache is None:
            rows = cls._read_json_list(cls.probability_score_table_path)
            cls._probability_rows_cache = {str(row.get("bucketId")): row for row in rows if row.get("bucketId")}
        return cls._probability_rows_cache

    @classmethod
    def _in_dynamic_universe(cls, pair: str, timestamp: Any) -> bool:
        if not pair or timestamp is None:
            return False
        try:
            timestamp_iso = timestamp.isoformat()
        except AttributeError:
            timestamp_iso = str(timestamp)
        return pair in get_pairs_for_timestamp(cls._universe_snapshots(), timestamp_iso)

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

        dataframe["quote_volume"] = dataframe["close"] * dataframe["volume"]
        dataframe["quote_volume_24h"] = dataframe["quote_volume"].rolling(24, min_periods=12).sum()
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

    @staticmethod
    def _add_basic_missing_columns(dataframe: DataFrame, columns: list[str]) -> DataFrame:
        for column in columns:
            dataframe[column] = np.nan
        return dataframe

    def _merge_pair_4h(self, dataframe: DataFrame, metadata: dict[str, Any]) -> DataFrame:
        pair = metadata.get("pair")
        if not pair or not getattr(self, "dp", None):
            dataframe = self._add_basic_missing_columns(dataframe, ["close_4h", "ema20_4h", "ema50_4h", "ema200_4h"])
            dataframe["pair_4h_data_missing"] = True
            return dataframe
        try:
            informative = self.dp.get_pair_dataframe(pair=pair, timeframe="4h")
        except Exception:
            informative = DataFrame()
        if informative.empty or "date" not in informative.columns:
            dataframe = self._add_basic_missing_columns(dataframe, ["close_4h", "ema20_4h", "ema50_4h", "ema200_4h"])
            dataframe["pair_4h_data_missing"] = True
            return dataframe
        informative = informative.copy()
        informative["ema20"] = informative["close"].ewm(span=20, adjust=False).mean()
        informative["ema50"] = informative["close"].ewm(span=50, adjust=False).mean()
        informative["ema200"] = informative["close"].ewm(span=200, adjust=False).mean()
        informative = informative[["date", "close", "ema20", "ema50", "ema200"]]
        dataframe = merge_informative_pair(dataframe, informative, self.timeframe, "4h", ffill=True)
        for column in ("close_4h", "ema20_4h", "ema50_4h", "ema200_4h"):
            if column not in dataframe.columns:
                dataframe[column] = np.nan
        dataframe["pair_4h_data_missing"] = dataframe[["close_4h", "ema20_4h", "ema50_4h", "ema200_4h"]].isna().any(axis=1)
        return dataframe

    def _merge_btc_1h(self, dataframe: DataFrame) -> DataFrame:
        if not getattr(self, "dp", None):
            dataframe = self._add_basic_missing_columns(dataframe, ["btc_close_1h", "btc_1h_return_3"])
            dataframe["btc_1h_data_missing"] = True
            return dataframe
        try:
            btc = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe="1h")
        except Exception:
            btc = DataFrame()
        if btc.empty or "date" not in btc.columns:
            dataframe = self._add_basic_missing_columns(dataframe, ["btc_close_1h", "btc_1h_return_3"])
            dataframe["btc_1h_data_missing"] = True
            return dataframe
        btc = btc.copy()
        btc["btc_close_1h"] = btc["close"]
        btc["btc_1h_return_3"] = (btc["close"] / btc["close"].shift(3)) - 1
        dataframe = dataframe.merge(btc[["date", "btc_close_1h", "btc_1h_return_3"]], on="date", how="left")
        dataframe["btc_1h_data_missing"] = dataframe[["btc_close_1h", "btc_1h_return_3"]].isna().any(axis=1)
        return dataframe

    def _merge_btc_4h(self, dataframe: DataFrame) -> DataFrame:
        if not getattr(self, "dp", None):
            dataframe = self._add_basic_missing_columns(dataframe, ["btc_close_4h", "btc_ema200_4h"])
            dataframe["btc_4h_data_missing"] = True
            return dataframe
        try:
            btc = self.dp.get_pair_dataframe(pair="BTC/USDT:USDT", timeframe="4h")
        except Exception:
            btc = DataFrame()
        if btc.empty or "date" not in btc.columns:
            dataframe = self._add_basic_missing_columns(dataframe, ["btc_close_4h", "btc_ema200_4h"])
            dataframe["btc_4h_data_missing"] = True
            return dataframe
        btc = btc.copy()
        btc["btc_close"] = btc["close"]
        btc["btc_ema200"] = btc["close"].ewm(span=200, adjust=False).mean()
        dataframe = merge_informative_pair(dataframe, btc[["date", "btc_close", "btc_ema200"]], self.timeframe, "4h", ffill=True)
        for column in ("btc_close_4h", "btc_ema200_4h"):
            if column not in dataframe.columns:
                dataframe[column] = np.nan
        dataframe["btc_4h_data_missing"] = dataframe[["btc_close_4h", "btc_ema200_4h"]].isna().any(axis=1)
        return dataframe

    @staticmethod
    def _btc_state(row: Series) -> str:
        if bool(row.get("btc_1h_data_missing", True)) or bool(row.get("btc_4h_data_missing", True)):
            return "unknown"
        return_3h = safe_float(row.get("btc_1h_return_3"))
        close_4h = safe_float(row.get("btc_close_4h"))
        ema200_4h = safe_float(row.get("btc_ema200_4h"))
        if return_3h is None or close_4h is None or ema200_4h is None:
            return "unknown"
        if return_3h <= -0.015:
            return "crash"
        if return_3h <= -0.008 or close_4h < ema200_4h:
            return "weak"
        return "safe"

    @staticmethod
    def _regime(row: Series) -> str:
        if bool(row.get("ap_dyn_audit_data_missing", True)):
            return "avoid"
        if safe_float(row.get("close_4h")) is None:
            return "avoid"
        strong_4h_downtrend = (
            safe_float(row.get("close_4h")) is not None
            and safe_float(row.get("ema200_4h")) is not None
            and safe_float(row.get("ema20_4h")) is not None
            and safe_float(row.get("ema50_4h")) is not None
            and row["close_4h"] < row["ema200_4h"]
            and row["ema20_4h"] < row["ema50_4h"]
        )
        if row.get("ap_dyn_btc_state") == "crash" or strong_4h_downtrend:
            return "avoid"
        return regime_candidate(
            row.get("close"),
            row.get("ema20"),
            row.get("ema50"),
            row.get("ema200"),
            row.get("rsi14"),
            row.get("atr_pct"),
            str(row.get("ap_dyn_btc_state", "unknown")),
        )

    @classmethod
    def _probability_bucket_for_row(cls, row: Series) -> str:
        return bucket_id(
            [
                str(row.get("ap_dyn_audit_regime", "unknown")),
                liquidity_bucket(row.get("quote_volume_24h")),
                volatility_bucket(row.get("atr_pct")),
                rsi_bucket(row.get("rsi14")),
                ema_distance_bucket(row.get("close"), row.get("ema20")),
                bollinger_position_bucket(row.get("close"), row.get("bb_lower"), row.get("bb_middle"), row.get("bb_upper")),
                str(row.get("ap_dyn_btc_state", "unknown")),
            ]
        )

    @classmethod
    def _probability_row_for_bucket(cls, bucket: str) -> dict[str, Any] | None:
        return cls._probability_rows().get(bucket)

    @classmethod
    def _probability_pass(cls, row: Series) -> bool:
        probability_row = cls._probability_row_for_bucket(str(row.get("ap_dyn_probability_bucket", "")))
        if not probability_row:
            return False
        return bool(
            probability_row.get("sampleCount", 0) >= cls.probability_min_samples
            and (safe_float(probability_row.get("profitFactor")) or 0) >= 1.2
            and (safe_float(probability_row.get("expectancy")) or 0) > 0
            and probability_row.get("decision") == "research_candidate"
        )

    @classmethod
    def _probability_sample_count(cls, row: Series) -> int:
        probability_row = cls._probability_row_for_bucket(str(row.get("ap_dyn_probability_bucket", "")))
        return int(probability_row.get("sampleCount", 0)) if probability_row else 0

    @staticmethod
    def _add_module_columns(dataframe: DataFrame) -> DataFrame:
        dataframe["ap_dyn_trend_base"] = (
            (dataframe["ap_dyn_audit_regime"] == "trend")
            & (dataframe["close_4h"] > dataframe["ema200_4h"])
            & (dataframe["ema20_4h"] > dataframe["ema50_4h"])
            & (dataframe["close"] > dataframe["ema50"])
            & (dataframe["ap_dyn_btc_state"] == "safe")
        )
        dataframe["ap_dyn_mean_reversion_base"] = (
            (dataframe["ap_dyn_audit_regime"] == "mean_reversion")
            & (dataframe["ap_dyn_btc_state"] != "crash")
            & (dataframe["close"] <= dataframe["bb_lower"] * 1.01)
            & (dataframe["rsi14"] <= 45)
            & (dataframe["atr_pct"] <= 0.08)
        )
        dataframe["ap_dyn_audit_trend_module_pass"] = (
            dataframe["ap_dyn_trend_base"]
            & (dataframe["close"] >= dataframe["ema20"] * 0.985)
            & (dataframe["close"] <= dataframe["ema20"] * 1.02)
            & (dataframe["close"] > dataframe["ema20"])
            & (dataframe["macd_histogram"] > dataframe["macd_histogram"].shift(1))
            & (dataframe["volume_ratio"] >= 1.1)
            & (dataframe["rsi14"] <= 65)
        )
        dataframe["ap_dyn_audit_mean_reversion_module_pass"] = (
            dataframe["ap_dyn_mean_reversion_base"]
            & (dataframe["close"] > dataframe["bb_lower"])
            & (dataframe["rsi14"] > dataframe["rsi14"].shift(1))
            & (dataframe["volume_ratio"] >= 0.7)
        )
        return dataframe

    @classmethod
    def _entry_conditions(cls, dataframe: DataFrame) -> Any:
        return (
            dataframe["ap_dyn_audit_in_dynamic_universe"]
            & (dataframe["ap_dyn_audit_regime"] != "avoid")
            & dataframe["ap_dyn_audit_probability_score_pass"]
            & dataframe["ap_dyn_audit_liquidity_gate_pass"]
            & (dataframe["ap_dyn_audit_trend_module_pass"] | dataframe["ap_dyn_audit_mean_reversion_module_pass"])
            & (dataframe["volume"] > 0)
            & ~dataframe["ap_dyn_audit_data_missing"]
        )

    @classmethod
    def _add_audit_columns(cls, dataframe: DataFrame, pair: str) -> DataFrame:
        required_columns = [
            "close",
            "ema20",
            "ema50",
            "ema200",
            "rsi14",
            "macd_histogram",
            "bb_lower",
            "bb_middle",
            "bb_upper",
            "atr_pct",
            "volume_ratio",
            "close_4h",
            "ema20_4h",
            "ema50_4h",
            "ema200_4h",
            "btc_1h_return_3",
            "btc_close_4h",
            "btc_ema200_4h",
        ]
        dataframe["ap_dyn_audit_data_missing"] = dataframe[required_columns].isna().any(axis=1)
        dataframe["ap_dyn_audit_in_dynamic_universe"] = dataframe["date"].apply(lambda value: cls._in_dynamic_universe(pair, value))
        dataframe["ap_dyn_btc_state"] = dataframe.apply(cls._btc_state, axis=1)
        dataframe["ap_dyn_audit_regime"] = dataframe.apply(cls._regime, axis=1)
        dataframe["ap_dyn_probability_bucket"] = dataframe.apply(cls._probability_bucket_for_row, axis=1)
        dataframe["ap_dyn_audit_probability_score_available"] = dataframe["ap_dyn_probability_bucket"].apply(
            lambda bucket: cls._probability_row_for_bucket(str(bucket)) is not None
        )
        dataframe["ap_dyn_audit_probability_sample_count"] = dataframe.apply(cls._probability_sample_count, axis=1)
        dataframe["ap_dyn_audit_probability_score_pass"] = dataframe.apply(cls._probability_pass, axis=1)

        dataframe["ap_dyn_audit_liquidity_gate_available"] = False
        dataframe["ap_dyn_audit_liquidity_gate_pass"] = cls.allow_liquidity_gate_fallback_for_backtest
        dataframe["ap_dyn_audit_liquidity_gate_decision"] = np.where(
            dataframe["ap_dyn_audit_liquidity_gate_pass"],
            "fallback_for_backtest_research_only",
            "blocked_no_public_liquidity_context",
        )

        dataframe = cls._add_module_columns(dataframe)
        dataframe["ap_dyn_audit_final_entry"] = cls._entry_conditions(dataframe)
        dataframe["ap_dyn_audit_skip_reason"] = np.select(
            [
                dataframe["ap_dyn_audit_final_entry"],
                dataframe["ap_dyn_audit_data_missing"],
                ~dataframe["ap_dyn_audit_in_dynamic_universe"],
                dataframe["ap_dyn_audit_regime"] == "avoid",
                ~dataframe["ap_dyn_audit_probability_score_available"],
                ~dataframe["ap_dyn_audit_probability_score_pass"],
                ~dataframe["ap_dyn_audit_liquidity_gate_pass"],
                ~(dataframe["ap_dyn_audit_trend_module_pass"] | dataframe["ap_dyn_audit_mean_reversion_module_pass"]),
            ],
            [
                "entry_signal_passed",
                "data_missing",
                "not_in_dynamic_universe",
                "avoid_regime",
                "probability_score_unavailable",
                "probability_score_not_passed",
                "liquidity_gate_not_passed",
                "module_conditions_not_passed",
            ],
            default="unknown",
        )
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = str(metadata.get("pair") or "")
        dataframe = self._add_core_indicators(dataframe)
        dataframe = self._merge_pair_4h(dataframe, metadata)
        dataframe = self._merge_btc_1h(dataframe)
        dataframe = self._merge_btc_4h(dataframe)
        dataframe = self._add_audit_columns(dataframe, pair)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = ""
        entry_conditions = self._entry_conditions(dataframe)
        dataframe.loc[entry_conditions, "enter_long"] = 1
        dataframe.loc[entry_conditions & dataframe["ap_dyn_audit_trend_module_pass"], "enter_tag"] = "dynamic_regime_trend_v01"
        dataframe.loc[entry_conditions & dataframe["ap_dyn_audit_mean_reversion_module_pass"], "enter_tag"] = "dynamic_regime_mean_reversion_v01"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_tag"] = ""
        return dataframe

    def _latest_histogram_weakness(self, pair: str, current_time: datetime) -> bool:
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
        age_hours = (current_time - open_date).total_seconds() / 3600
        entry_tag = str(getattr(trade, "enter_tag", "") or "")
        if "mean_reversion" in entry_tag:
            if current_profit >= 0.025:
                return "mean_reversion_target"
            if age_hours >= 8 and current_profit <= 0:
                return "mean_reversion_time_stop"
        if age_hours >= 12 and current_profit <= 0:
            return "trend_time_stop_12h_not_profitable"
        if current_profit > 0 and self._latest_histogram_weakness(pair, current_time):
            return "trend_profitable_macd_weakness_exit"
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
