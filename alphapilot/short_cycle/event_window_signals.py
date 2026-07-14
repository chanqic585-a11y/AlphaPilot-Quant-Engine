"""Closed-candle event-window signals and non-executable near-miss diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


EVENT_WINDOW_SIGNAL_FAMILIES = frozenset(
    {
        "windowed_trend_reclaim_long",
        "windowed_breakout_retest_long",
        "windowed_liquidity_sweep_reclaim_long",
        "windowed_recovery_reclaim_long",
        "windowed_squeeze_breakout_long",
        "windowed_upper_band_rejection_short",
        "windowed_failed_breakout_short",
        "windowed_failed_reclaim_short",
    }
)


@dataclass(frozen=True)
class EventWindowSignalEvaluation:
    signal: pd.Series
    nearMiss: pd.Series
    direction: str
    checks: dict[str, pd.Series]
    eventAge: pd.Series
    executionIntentCount: int = 0

    def failed_checks(self, index: int) -> tuple[str, ...]:
        return tuple(
            name for name, values in self.checks.items() if not bool(values.iloc[index])
        )


def _ready(frame: pd.DataFrame) -> pd.Series:
    columns = ("ema20", "ema50", "ema200", "rsi14", "atr14", "volume_ratio")
    return frame.loc[:, columns].notna().all(axis=1)


def _or_window(conditions: list[pd.Series], index: pd.Index) -> tuple[pd.Series, pd.Series]:
    matched = pd.Series(False, index=index)
    age = pd.Series(np.nan, index=index, dtype=float)
    for offset, condition in enumerate(conditions, start=1):
        current = condition.fillna(False)
        age = age.mask(current & age.isna(), float(offset))
        matched |= current
    return matched, age


def _volume_guard(frame: pd.DataFrame, params: dict[str, Any], *, prefix: str = "") -> pd.Series:
    minimum = float(params[f"{prefix}volume_min"])
    maximum = float(params[f"{prefix}volume_max"])
    return frame["volume_ratio"].between(minimum, maximum)


def _btc_guard(
    frame: pd.DataFrame,
    params: dict[str, Any],
    *,
    direction: str,
) -> pd.Series:
    threshold = params.get("btc_shock_threshold")
    if threshold is None:
        block_column = "btc_long_block" if direction == "long" else "btc_short_block"
        return ~frame[block_column]
    threshold = float(threshold)
    if threshold <= 0:
        raise ValueError("btc_shock_threshold_must_be_positive")
    returns = frame["btc_ret_3"]
    if direction == "long":
        return returns.notna() & (returns > -threshold)
    return returns.notna() & (returns < threshold)


def _learned_factor_guard(
    frame: pd.DataFrame,
    params: dict[str, Any],
    *,
    direction: str,
) -> pd.Series:
    """Apply only pre-registered transparent factors; absent bounds are neutral."""

    sign = 1.0 if direction == "long" else -1.0
    lookback = int(params.get("factor_lookback") or 12)
    builders = {
        "aligned_trend20_50": lambda: sign * (frame["ema20"] / frame["ema50"] - 1),
        "aligned_trend50_200": lambda: sign * (frame["ema50"] / frame["ema200"] - 1),
        "aligned_slope20": lambda: sign
        * (frame["ema20"] / frame["ema20"].shift(lookback) - 1),
        "aligned_return": lambda: sign
        * (frame["close"] / frame["close"].shift(lookback) - 1),
        "btc_aligned": lambda: sign * frame["btc_ret_3"],
        "btc_trend20_50": lambda: sign * frame["btc_trend20_50"],
        "btc_trend50_200": lambda: sign * frame["btc_trend50_200"],
        "btc_slope20_12": lambda: sign * frame["btc_slope20_12"],
        "atr_pct": lambda: frame["atr14"] / frame["close"].replace(0, np.nan),
    }
    guard = pd.Series(True, index=frame.index)
    for name, build_values in builders.items():
        minimum = params.get(f"{name}_min")
        maximum = params.get(f"{name}_max")
        quantile_min = params.get(f"{name}_quantile_min")
        quantile_max = params.get(f"{name}_quantile_max")
        if (
            minimum is None
            and maximum is None
            and quantile_min is None
            and quantile_max is None
        ):
            continue
        try:
            values = build_values()
        except KeyError:
            guard &= False
            continue
        if minimum is not None:
            guard &= values >= float(minimum)
        if maximum is not None:
            guard &= values <= float(maximum)
        if quantile_min is not None or quantile_max is not None:
            window = int(params.get("adaptive_factor_window") or 0)
            if window < 20:
                raise ValueError("adaptive_factor_window_must_be_at_least_twenty")
            if quantile_min is not None:
                quantile = float(quantile_min)
                if not 0 <= quantile <= 1:
                    raise ValueError("adaptive_factor_quantile_out_of_range")
                threshold = (
                    values.rolling(window, min_periods=window)
                    .quantile(quantile)
                    .shift(1)
                )
                guard &= values >= threshold
            if quantile_max is not None:
                quantile = float(quantile_max)
                if not 0 <= quantile <= 1:
                    raise ValueError("adaptive_factor_quantile_out_of_range")
                threshold = (
                    values.rolling(window, min_periods=window)
                    .quantile(quantile)
                    .shift(1)
                )
                guard &= values <= threshold
    return guard.fillna(False)


def _evaluation(
    *,
    checks: dict[str, pd.Series],
    direction: str,
    event_age: pd.Series,
    max_shadow_failures: int,
    required_check_names: tuple[str, ...] = (),
    minimum_optional_checks: int | None = None,
) -> EventWindowSignalEvaluation:
    normalized = {name: values.fillna(False).astype(bool) for name, values in checks.items()}
    if minimum_optional_checks is None:
        passed = sum(values.astype(int) for values in normalized.values())
        failure_deficit = len(normalized) - passed
        signal = failure_deficit.eq(0)
    else:
        missing_required = set(required_check_names) - set(normalized)
        if missing_required:
            raise ValueError(
                "event_window_required_checks_missing:"
                + ",".join(sorted(missing_required))
            )
        optional_names = tuple(
            name for name in normalized if name not in required_check_names
        )
        minimum_optional_checks = int(minimum_optional_checks)
        if not 0 <= minimum_optional_checks <= len(optional_names):
            raise ValueError("minimum_optional_checks_out_of_range")
        required_passed = pd.Series(True, index=next(iter(normalized.values())).index)
        for name in required_check_names:
            required_passed &= normalized[name]
        optional_passed = sum(normalized[name].astype(int) for name in optional_names)
        optional_deficit = (minimum_optional_checks - optional_passed).clip(lower=0)
        required_deficit = sum(
            (~normalized[name]).astype(int) for name in required_check_names
        )
        failure_deficit = required_deficit + optional_deficit
        signal = required_passed & optional_passed.ge(minimum_optional_checks)
    near_miss = (~signal) & failure_deficit.between(1, max_shadow_failures)
    return EventWindowSignalEvaluation(
        signal=signal.fillna(False),
        nearMiss=near_miss.fillna(False),
        direction=direction,
        checks=normalized,
        eventAge=event_age,
    )


def evaluate_event_window_signal(
    frame: pd.DataFrame,
    family: str,
    params: dict[str, Any],
    *,
    max_shadow_failures: int = 2,
) -> EventWindowSignalEvaluation:
    if family not in EVENT_WINDOW_SIGNAL_FAMILIES:
        raise ValueError(f"event_window_family_not_supported:{family}")
    window = int(params["event_window"])
    if window not in (2, 3, 4, 5):
        raise ValueError("event_window_must_be_between_two_and_five")

    ready = _ready(frame)
    atr_pct = frame["atr14"] / frame["close"].replace(0, np.nan)
    volatility = atr_pct.between(params["atr_pct_min"], params["atr_pct_max"])
    required_check_names = (
        "data_ready",
        "btc_guard",
        "event_window",
        "volatility_guard",
        "learned_factor_guard",
    )
    minimum_optional_checks = params.get("minimum_optional_checks")

    if family == "windowed_trend_reclaim_long":
        events = [
            (frame["low"].shift(lag) <= frame["ema20"].shift(lag) * (1 + params["pullback_tolerance"]))
            & (frame["close"].shift(lag) <= frame["ema20"].shift(lag) * (1 + params["reclaim_buffer"]))
            for lag in range(1, window + 1)
        ]
        event, age = _or_window(events, frame.index)
        checks = {
            "data_ready": ready,
            "btc_guard": _btc_guard(frame, params, direction="long"),
            "event_window": event,
            "trend_regime": (frame["ema20"] >= frame["ema50"] * params["trend_tolerance"])
            & (frame["ema50"] >= frame["ema200"] * params["trend_tolerance"])
            & (frame["ema20"] > frame["ema20"].shift(params["ema_slope_lookback"])),
            "level_reclaim": frame["close"] > frame["ema20"] * (1 + params["reclaim_buffer"]),
            "confirmation_candle": (frame["close"] > frame["open"])
            & (frame["close"] > frame["high"].shift(1)),
            "momentum_guard": frame["rsi14"].between(params["rsi_min"], params["rsi_max"])
            & (frame["rsi14"] >= frame["rsi14"].shift(1)),
            "volume_guard": _volume_guard(frame, params),
            "volatility_guard": volatility,
            "learned_factor_guard": _learned_factor_guard(
                frame, params, direction="long"
            ),
        }
        return _evaluation(
            checks=checks,
            direction="long",
            event_age=age,
            max_shadow_failures=max_shadow_failures,
            required_check_names=required_check_names,
            minimum_optional_checks=minimum_optional_checks,
        )

    if family == "windowed_breakout_retest_long":
        events = []
        for lag in range(1, window + 1):
            ceiling = frame["high"].rolling(params["lookback"], min_periods=params["lookback"]).max().shift(lag + 1)
            events.append(
                (frame["close"].shift(lag) > ceiling * (1 + params["breakout_buffer"]))
                & (frame["volume_ratio"].shift(lag) >= params["breakout_volume_min"])
                & (frame["low"] <= ceiling * (1 + params["retest_tolerance"]))
                & (frame["close"] >= ceiling * (1 + params["reclaim_buffer"]))
            )
        event, age = _or_window(events, frame.index)
        checks = {
            "data_ready": ready,
            "btc_guard": _btc_guard(frame, params, direction="long"),
            "event_window": event,
            "trend_regime": (frame["ema20"] >= frame["ema50"] * params["trend_tolerance"])
            & (frame["ema50"] >= frame["ema200"] * params["trend_tolerance"]),
            "confirmation_candle": frame["close"] > frame["open"],
            "momentum_guard": frame["rsi14"].between(params["rsi_min"], params["rsi_max"]),
            "volume_guard": frame["volume_ratio"].between(
                params["confirmation_volume_min"], params["confirmation_volume_max"]
            ),
            "volatility_guard": volatility,
            "learned_factor_guard": _learned_factor_guard(
                frame, params, direction="long"
            ),
        }
        return _evaluation(
            checks=checks,
            direction="long",
            event_age=age,
            max_shadow_failures=max_shadow_failures,
            required_check_names=required_check_names,
            minimum_optional_checks=minimum_optional_checks,
        )

    if family == "windowed_liquidity_sweep_reclaim_long":
        events = []
        for lag in range(1, window + 1):
            floor = frame["low"].rolling(params["lookback"], min_periods=params["lookback"]).min().shift(lag + 1)
            events.append(
                (frame["low"].shift(lag) <= floor * (1 - params["sweep_buffer"]))
                & (frame["rsi14"].shift(lag) <= params["rsi_oversold"])
                & (frame["close"] >= floor * (1 + params["reclaim_buffer"]))
            )
        event, age = _or_window(events, frame.index)
        checks = {
            "data_ready": ready,
            "btc_guard": _btc_guard(frame, params, direction="long"),
            "event_window": event,
            "trend_regime": frame["close"] >= frame["ema200"] * params["trend_floor"],
            "confirmation_candle": (frame["close"] > frame["open"])
            & (frame["close"] > frame["high"].shift(1)),
            "momentum_guard": (frame["rsi14"] >= params["rsi_recovery_min"])
            & (frame["rsi14"] > frame["rsi14"].shift(1)),
            "volume_guard": _volume_guard(frame, params),
            "volatility_guard": volatility,
            "learned_factor_guard": _learned_factor_guard(
                frame, params, direction="long"
            ),
        }
        return _evaluation(
            checks=checks,
            direction="long",
            event_age=age,
            max_shadow_failures=max_shadow_failures,
            required_check_names=required_check_names,
            minimum_optional_checks=minimum_optional_checks,
        )

    if family == "windowed_recovery_reclaim_long":
        events = [
            frame["close"].shift(lag) <= frame["ema20"].shift(lag)
            for lag in range(1, window + 1)
        ]
        event, age = _or_window(events, frame.index)
        checks = {
            "data_ready": ready,
            "btc_guard": _btc_guard(frame, params, direction="long"),
            "event_window": event,
            "btc_bull_regime": (frame["btc_trend20_50"] > 0)
            & (frame["btc_trend50_200"] > -0.01),
            "trend_regime": frame["close"] >= frame["ema200"] * params["trend_floor"],
            "level_reclaim": frame["close"] > frame["ema20"],
            "confirmation_candle": (frame["close"] > frame["open"])
            | (frame["macd_hist"] > frame["macd_hist"].shift(1)),
            "momentum_guard": frame["rsi14"].between(
                params["rsi_min"], params["rsi_max"]
            ),
            "volume_guard": _volume_guard(frame, params),
            "volatility_guard": volatility,
            "learned_factor_guard": _learned_factor_guard(
                frame, params, direction="long"
            ),
        }
        return _evaluation(
            checks=checks,
            direction="long",
            event_age=age,
            max_shadow_failures=max_shadow_failures,
            required_check_names=required_check_names,
            minimum_optional_checks=minimum_optional_checks,
        )

    if family == "windowed_squeeze_breakout_long":
        squeeze_window = int(params["squeeze_window"])
        squeeze_baseline = frame["bb_width"].rolling(
            squeeze_window, min_periods=squeeze_window
        ).median()
        events = [
            frame["bb_width"].shift(lag)
            <= squeeze_baseline.shift(lag + 1) * params["squeeze_ratio"]
            for lag in range(1, window + 1)
        ]
        compression, age = _or_window(events, frame.index)
        ceiling = frame["high"].rolling(
            int(params["lookback"]), min_periods=int(params["lookback"])
        ).max().shift(1)
        breakout = frame["close"] > ceiling * (1 + params["breakout_buffer"])
        checks = {
            "data_ready": ready,
            "btc_guard": _btc_guard(frame, params, direction="long"),
            "event_window": compression & breakout,
            "trend_regime": frame["close"]
            >= frame["ema200"] * params["trend_tolerance"],
            "confirmation_candle": frame["close"] > frame["open"],
            "momentum_guard": frame["rsi14"].between(
                params["rsi_min"], params["rsi_max"]
            ),
            "volume_guard": _volume_guard(frame, params),
            "volatility_expansion": frame["bb_width"]
            > frame["bb_width"].shift(1),
            "volatility_guard": volatility,
            "learned_factor_guard": _learned_factor_guard(
                frame, params, direction="long"
            ),
        }
        return _evaluation(
            checks=checks,
            direction="long",
            event_age=age,
            max_shadow_failures=max_shadow_failures,
            required_check_names=required_check_names,
            minimum_optional_checks=minimum_optional_checks,
        )

    if family == "windowed_upper_band_rejection_short":
        events = [
            (
                frame["high"].shift(lag)
                >= frame["bb_upper"].shift(lag) * (1 - params["upper_buffer"])
            )
            & (frame["rsi14"].shift(lag) >= params["rsi_high"])
            for lag in range(1, window + 1)
        ]
        event, age = _or_window(events, frame.index)
        checks = {
            "data_ready": ready,
            "btc_guard": _btc_guard(frame, params, direction="short"),
            "event_window": event,
            "trend_regime": (
                frame["close"] <= frame["ema200"] * params["trend_tolerance"]
            )
            & (frame["ema20"] <= frame["ema50"] * params["trend_tolerance"]),
            "confirmation_candle": frame["close"] < frame["open"],
            "momentum_guard": (
                frame["rsi14"] <= params["rsi_reversal_max"]
            )
            & (frame["rsi14"] < frame["rsi14"].shift(1)),
            "volume_guard": _volume_guard(frame, params),
            "volatility_guard": volatility,
            "learned_factor_guard": _learned_factor_guard(
                frame, params, direction="short"
            ),
        }
        return _evaluation(
            checks=checks,
            direction="short",
            event_age=age,
            max_shadow_failures=max_shadow_failures,
            required_check_names=required_check_names,
            minimum_optional_checks=minimum_optional_checks,
        )

    if family == "windowed_failed_breakout_short":
        events = []
        for lag in range(1, window + 1):
            ceiling = frame["high"].rolling(params["lookback"], min_periods=params["lookback"]).max().shift(lag + 1)
            events.append(
                (frame["high"].shift(lag) >= ceiling * (1 + params["sweep_buffer"]))
                & (frame["rsi14"].shift(lag) >= params["rsi_high"])
                & (frame["close"] <= ceiling * (1 - params["rejection_buffer"]))
            )
        event, age = _or_window(events, frame.index)
        checks = {
            "data_ready": ready,
            "btc_guard": _btc_guard(frame, params, direction="short"),
            "event_window": event,
            "trend_regime": frame["close"] <= frame["ema200"] * params["trend_ceiling"],
            "confirmation_candle": (frame["close"] < frame["open"])
            & (frame["low"] < frame["low"].shift(1)),
            "momentum_guard": (frame["rsi14"] <= params["rsi_reversal_max"])
            & (frame["rsi14"] < frame["rsi14"].shift(1)),
            "volume_guard": _volume_guard(frame, params),
            "volatility_guard": volatility,
            "learned_factor_guard": _learned_factor_guard(
                frame, params, direction="short"
            ),
        }
        return _evaluation(
            checks=checks,
            direction="short",
            event_age=age,
            max_shadow_failures=max_shadow_failures,
            required_check_names=required_check_names,
            minimum_optional_checks=minimum_optional_checks,
        )

    events = [
        (frame["high"].shift(lag) >= frame["ema20"].shift(lag) * (1 - params["reclaim_tolerance"]))
        & (frame["close"].shift(lag) >= frame["ema20"].shift(lag) * (1 - params["reclaim_tolerance"]))
        for lag in range(1, window + 1)
    ]
    event, age = _or_window(events, frame.index)
    checks = {
        "data_ready": ready,
        "btc_guard": _btc_guard(frame, params, direction="short"),
        "event_window": event,
        "trend_regime": (frame["ema20"] <= frame["ema50"] * params["trend_tolerance"])
        & (frame["ema50"] <= frame["ema200"] * params["trend_tolerance"])
        & (frame["ema20"] < frame["ema20"].shift(params["ema_slope_lookback"])),
        "level_rejection": frame["close"] < frame["ema20"] * (1 - params["rejection_buffer"]),
        "confirmation_candle": (frame["close"] < frame["open"])
        & (frame["close"] < frame["low"].shift(1)),
        "momentum_guard": (frame["macd_hist"] < 0)
        & frame["rsi14"].between(params["rsi_min"], params["rsi_max"]),
        "volume_guard": _volume_guard(frame, params),
        "volatility_guard": volatility,
        "learned_factor_guard": _learned_factor_guard(
            frame, params, direction="short"
        ),
    }
    return _evaluation(
        checks=checks,
        direction="short",
        event_age=age,
        max_shadow_failures=max_shadow_failures,
        required_check_names=required_check_names,
        minimum_optional_checks=minimum_optional_checks,
    )
