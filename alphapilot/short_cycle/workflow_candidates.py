"""Immutable V13.27.3 short-cycle workflow candidate definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_REQUIRED_PARAMETERS = {
    "breakout_volume_long": {
        "lookback",
        "breakout_buffer",
        "rsi_max",
        "volume_min",
    },
    "ema_reclaim_long": {
        "trend_tolerance",
        "reclaim_buffer",
        "rsi_min",
        "rsi_max",
        "volume_min",
    },
    "mean_reversion_reclaim_long": {
        "rsi_low",
        "volume_min",
        "max_range_pct",
    },
    "short_breakdown_momentum": {
        "lookback",
        "trend_tolerance",
        "breakdown_buffer",
        "rsi_max",
        "volume_min",
    },
    "short_rejection": {
        "upper_buffer",
        "trend_tolerance",
        "rsi_high",
        "volume_min",
    },
    "momentum_continuation_long": {
        "trend_tolerance",
        "macd_tolerance",
        "rsi_min",
        "rsi_max",
        "volume_min",
    },
    "squeeze_breakout_long": {
        "lookback",
        "squeeze_window",
        "squeeze_ratio",
        "volume_min",
    },
}


@dataclass(frozen=True)
class ShortCycleWorkflowCandidate:
    familyKey: str
    displayName: str
    timeframe: str
    direction: str
    signalFamily: str
    parameters: dict[str, Any]

    def definition(self) -> dict[str, Any]:
        parameters = dict(self.parameters)
        return {
            "schemaVersion": "short_cycle_strategy_definition_v1",
            "signalEngine": "short_cycle_v1",
            "signalFamily": self.signalFamily,
            "market": "crypto_usdt_swap",
            "marketDataAccess": "public",
            "universePolicy": "point_in_time_dynamic_liquid_usdt_swap",
            "formalUniverseTarget": 50,
            "timeframe": self.timeframe,
            "direction": self.direction,
            "targetR": 2.0,
            "researchOnly": True,
            "executionEnabled": False,
            "forwardSignalPolicy": {
                "schemaVersion": "short_cycle_forward_policy_v1",
                "signalEngine": "short_cycle_v1",
                "signalFamily": self.signalFamily,
                "timeframe": self.timeframe,
                "direction": self.direction,
                "parameters": parameters,
            },
            "backtest": {
                "costModel": {"feeRate": 0.0005, "slippageRate": 0.0005},
            },
        }


def _candidate(
    family_key: str,
    display_name: str,
    timeframe: str,
    direction: str,
    signal_family: str,
    **parameters: Any,
) -> ShortCycleWorkflowCandidate:
    return ShortCycleWorkflowCandidate(
        familyKey=family_key,
        displayName=display_name,
        timeframe=timeframe,
        direction=direction,
        signalFamily=signal_family,
        parameters=parameters,
    )


_CANDIDATES = (
    _candidate(
        "short_cycle_5m_breakout_volume_long_v1",
        "5m 放量突破延续 ATR1.2",
        "5m",
        "long",
        "breakout_volume_long",
        lookback=48,
        breakout_buffer=0.001,
        rsi_max=78,
        volume_min=1.8,
        stop_atr=1.2,
        max_hold=24,
    ),
    _candidate(
        "short_cycle_5m_ema_reclaim_long_v1",
        "5m EMA20 回收反弹 ATR1.2",
        "5m",
        "long",
        "ema_reclaim_long",
        trend_tolerance=0.995,
        reclaim_buffer=0.002,
        rsi_min=42,
        rsi_max=68,
        volume_min=1.0,
        stop_atr=1.2,
        max_hold=24,
    ),
    _candidate(
        "short_cycle_5m_mean_reversion_reclaim_long_v1",
        "5m 极端超卖收回 ATR1.2",
        "5m",
        "long",
        "mean_reversion_reclaim_long",
        rsi_low=28,
        volume_min=1.0,
        max_range_pct=0.03,
        stop_atr=1.2,
        max_hold=18,
    ),
    _candidate(
        "short_cycle_5m_short_breakdown_momentum_v1",
        "5m 跌破放量延续 ATR1.2",
        "5m",
        "short",
        "short_breakdown_momentum",
        lookback=32,
        trend_tolerance=1.0,
        breakdown_buffer=0.001,
        rsi_max=48,
        volume_min=1.2,
        stop_atr=1.2,
        max_hold=24,
    ),
    _candidate(
        "short_cycle_5m_short_rejection_v1",
        "5m 上影拒绝回落 ATR1.2",
        "5m",
        "short",
        "short_rejection",
        upper_buffer=0.003,
        trend_tolerance=1.005,
        rsi_high=60,
        volume_min=1.1,
        stop_atr=1.2,
        max_hold=24,
    ),
    _candidate(
        "short_cycle_15m_momentum_continuation_long_v1",
        "15m 趋势动量延续 ATR1.4",
        "15m",
        "long",
        "momentum_continuation_long",
        trend_tolerance=1.0,
        macd_tolerance=0.8,
        rsi_min=48,
        rsi_max=72,
        volume_min=1.0,
        stop_atr=1.4,
        max_hold=16,
    ),
    _candidate(
        "short_cycle_15m_ema_reclaim_long_v1",
        "15m EMA20 回收反弹 ATR1.4",
        "15m",
        "long",
        "ema_reclaim_long",
        trend_tolerance=0.995,
        reclaim_buffer=0.003,
        rsi_min=42,
        rsi_max=72,
        volume_min=1.0,
        stop_atr=1.4,
        max_hold=16,
    ),
    _candidate(
        "short_cycle_15m_squeeze_breakout_long_v1",
        "15m 低波压缩突破 ATR1.4",
        "15m",
        "long",
        "squeeze_breakout_long",
        lookback=32,
        squeeze_window=96,
        squeeze_ratio=0.8,
        volume_min=1.2,
        stop_atr=1.4,
        max_hold=16,
    ),
    _candidate(
        "short_cycle_15m_short_breakdown_momentum_v1",
        "15m 跌破放量延续 ATR1.4",
        "15m",
        "short",
        "short_breakdown_momentum",
        lookback=32,
        trend_tolerance=1.0,
        breakdown_buffer=0.001,
        rsi_max=50,
        volume_min=1.1,
        stop_atr=1.4,
        max_hold=16,
    ),
    _candidate(
        "short_cycle_15m_short_rejection_v1",
        "15m 上影拒绝回落 ATR1.4",
        "15m",
        "short",
        "short_rejection",
        upper_buffer=0.003,
        trend_tolerance=1.005,
        rsi_high=60,
        volume_min=1.1,
        stop_atr=1.4,
        max_hold=16,
    ),
)


def _validate_candidates(
    candidates: tuple[ShortCycleWorkflowCandidate, ...],
) -> None:
    if len(candidates) != 10:
        raise ValueError("short_cycle_candidate_count_must_equal_10")
    if len({item.familyKey for item in candidates}) != len(candidates):
        raise ValueError("short_cycle_family_keys_must_be_unique")
    if len({item.displayName for item in candidates}) != len(candidates):
        raise ValueError("short_cycle_display_names_must_be_unique")
    for item in candidates:
        if item.timeframe not in {"5m", "15m"}:
            raise ValueError(f"short_cycle_timeframe_not_supported:{item.timeframe}")
        if item.direction not in {"long", "short"}:
            raise ValueError(f"short_cycle_direction_not_supported:{item.direction}")
        required = _REQUIRED_PARAMETERS.get(item.signalFamily)
        if required is None:
            raise ValueError(f"short_cycle_family_not_supported:{item.signalFamily}")
        missing = sorted(required - set(item.parameters))
        if missing:
            raise ValueError(
                f"short_cycle_parameters_missing:{item.familyKey}:{','.join(missing)}"
            )
        if float(item.parameters.get("stop_atr") or 0) <= 0:
            raise ValueError(f"short_cycle_stop_atr_invalid:{item.familyKey}")
        if int(item.parameters.get("max_hold") or 0) <= 0:
            raise ValueError(f"short_cycle_max_hold_invalid:{item.familyKey}")


_validate_candidates(_CANDIDATES)


def short_cycle_workflow_candidates() -> tuple[ShortCycleWorkflowCandidate, ...]:
    return _CANDIDATES
