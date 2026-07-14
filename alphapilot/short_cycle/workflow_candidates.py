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
    "trend_pullback_confirmation_long": {
        "pullback_lookback",
        "pullback_tolerance",
        "ema_slope_lookback",
        "trend_tolerance",
        "reclaim_buffer",
        "rsi_min",
        "rsi_max",
        "volume_min",
        "atr_pct_min",
        "atr_pct_max",
    },
    "compression_release_long": {
        "lookback",
        "squeeze_window",
        "squeeze_ratio",
        "expansion_min",
        "trend_tolerance",
        "rsi_max",
        "volume_min",
        "atr_pct_max",
    },
    "failed_reclaim_short": {
        "reclaim_lookback",
        "reclaim_tolerance",
        "rejection_buffer",
        "ema_slope_lookback",
        "trend_tolerance",
        "rsi_min",
        "rsi_max",
        "volume_min",
        "atr_pct_min",
        "atr_pct_max",
    },
    "liquidity_sweep_reclaim_long": {
        "lookback",
        "sweep_buffer",
        "reclaim_buffer",
        "trend_floor",
        "rsi_oversold",
        "rsi_recovery_min",
        "volume_min",
        "atr_pct_min",
        "atr_pct_max",
    },
    "breakout_retest_continuation_long": {
        "lookback",
        "breakout_buffer",
        "retest_tolerance",
        "reclaim_buffer",
        "trend_tolerance",
        "rsi_min",
        "rsi_max",
        "breakout_volume_min",
        "confirmation_volume_min",
        "retest_volume_ratio_max",
        "atr_pct_min",
        "atr_pct_max",
    },
    "failed_breakout_reversal_short": {
        "lookback",
        "sweep_buffer",
        "rejection_buffer",
        "trend_ceiling",
        "rsi_high",
        "volume_min",
        "atr_pct_min",
        "atr_pct_max",
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
    exitPolicy: str = "fixed_target_full_exit_v1"
    researchMetadata: dict[str, Any] | None = None
    formalDataPlan: dict[str, str | None] | None = None

    def definition(self) -> dict[str, Any]:
        parameters = dict(self.parameters)
        definition = {
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
            "exitPolicy": self.exitPolicy,
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
        if self.researchMetadata:
            definition["researchMetadata"] = dict(self.researchMetadata)
        if self.formalDataPlan:
            definition["formalDataPlan"] = dict(self.formalDataPlan)
        return definition


def _candidate(
    family_key: str,
    display_name: str,
    timeframe: str,
    direction: str,
    signal_family: str,
    exit_policy: str = "fixed_target_full_exit_v1",
    **parameters: Any,
) -> ShortCycleWorkflowCandidate:
    return ShortCycleWorkflowCandidate(
        familyKey=family_key,
        displayName=display_name,
        timeframe=timeframe,
        direction=direction,
        signalFamily=signal_family,
        parameters=parameters,
        exitPolicy=exit_policy,
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


_REDESIGNED_CANDIDATES = (
    _candidate(
        "short_cycle_redesign_5m_trend_pullback_confirmation_long_v1",
        "5m 顺势回踩确认 ATR1.0",
        "5m",
        "long",
        "trend_pullback_confirmation_long",
        exit_policy="two_r_half_atr_runner_v1",
        pullback_lookback=6,
        pullback_tolerance=0.0025,
        ema_slope_lookback=6,
        trend_tolerance=1.0,
        reclaim_buffer=0.0005,
        rsi_min=44,
        rsi_max=64,
        volume_min=1.15,
        atr_pct_min=0.002,
        atr_pct_max=0.018,
        stop_atr=1.0,
        max_hold=24,
    ),
    _candidate(
        "short_cycle_redesign_5m_compression_release_long_v1",
        "5m 压缩放量释放 ATR1.1",
        "5m",
        "long",
        "compression_release_long",
        exit_policy="two_r_half_atr_runner_v1",
        lookback=36,
        squeeze_window=96,
        squeeze_ratio=0.72,
        expansion_min=1.08,
        trend_tolerance=1.0,
        rsi_max=72,
        volume_min=1.8,
        atr_pct_max=0.022,
        stop_atr=1.1,
        max_hold=24,
    ),
    _candidate(
        "short_cycle_redesign_5m_failed_reclaim_short_v1",
        "5m 弱势反抽失败 ATR1.0",
        "5m",
        "short",
        "failed_reclaim_short",
        exit_policy="two_r_half_atr_runner_v1",
        reclaim_lookback=6,
        reclaim_tolerance=0.003,
        rejection_buffer=0.0005,
        ema_slope_lookback=6,
        trend_tolerance=1.0,
        rsi_min=36,
        rsi_max=58,
        volume_min=1.15,
        atr_pct_min=0.002,
        atr_pct_max=0.018,
        stop_atr=1.0,
        max_hold=24,
    ),
    _candidate(
        "short_cycle_redesign_15m_trend_pullback_confirmation_long_v1",
        "15m 顺势回踩确认 ATR1.2",
        "15m",
        "long",
        "trend_pullback_confirmation_long",
        exit_policy="two_r_half_atr_runner_v1",
        pullback_lookback=5,
        pullback_tolerance=0.004,
        ema_slope_lookback=4,
        trend_tolerance=1.0,
        reclaim_buffer=0.0005,
        rsi_min=42,
        rsi_max=66,
        volume_min=1.1,
        atr_pct_min=0.003,
        atr_pct_max=0.025,
        stop_atr=1.2,
        max_hold=16,
    ),
    _candidate(
        "short_cycle_redesign_15m_compression_release_long_v1",
        "15m 压缩放量释放 ATR1.3",
        "15m",
        "long",
        "compression_release_long",
        exit_policy="two_r_half_atr_runner_v1",
        lookback=28,
        squeeze_window=72,
        squeeze_ratio=0.75,
        expansion_min=1.08,
        trend_tolerance=1.0,
        rsi_max=74,
        volume_min=1.6,
        atr_pct_max=0.03,
        stop_atr=1.3,
        max_hold=16,
    ),
    _candidate(
        "short_cycle_redesign_15m_failed_reclaim_short_v1",
        "15m 弱势反抽失败 ATR1.2",
        "15m",
        "short",
        "failed_reclaim_short",
        exit_policy="two_r_half_atr_runner_v1",
        reclaim_lookback=5,
        reclaim_tolerance=0.005,
        rejection_buffer=0.0005,
        ema_slope_lookback=4,
        trend_tolerance=1.0,
        rsi_min=34,
        rsi_max=60,
        volume_min=1.1,
        atr_pct_min=0.003,
        atr_pct_max=0.025,
        stop_atr=1.2,
        max_hold=16,
    ),
)


_EVIDENCE_REDESIGNED_CANDIDATES = (
    _candidate(
        "short_cycle_evidence_5m_liquidity_sweep_reclaim_long_v1",
        "5m 流动性扫低收回 ATR1.0",
        "5m",
        "long",
        "liquidity_sweep_reclaim_long",
        exit_policy="two_r_half_atr_runner_v1",
        lookback=96,
        sweep_buffer=0.0015,
        reclaim_buffer=0.0005,
        trend_floor=0.965,
        rsi_oversold=38,
        rsi_recovery_min=36,
        volume_min=1.4,
        atr_pct_min=0.002,
        atr_pct_max=0.025,
        stop_atr=1.0,
        max_hold=36,
    ),
    _candidate(
        "short_cycle_evidence_5m_breakout_retest_continuation_long_v1",
        "5m 突破回踩确认 ATR1.0",
        "5m",
        "long",
        "breakout_retest_continuation_long",
        exit_policy="two_r_half_atr_runner_v1",
        lookback=96,
        breakout_buffer=0.001,
        retest_tolerance=0.003,
        reclaim_buffer=0.0003,
        trend_tolerance=1.0,
        rsi_min=48,
        rsi_max=70,
        breakout_volume_min=1.8,
        confirmation_volume_min=0.8,
        retest_volume_ratio_max=0.8,
        atr_pct_min=0.002,
        atr_pct_max=0.022,
        stop_atr=1.0,
        max_hold=36,
    ),
    _candidate(
        "short_cycle_evidence_5m_failed_breakout_reversal_short_v1",
        "5m 假突破反转 ATR1.0",
        "5m",
        "short",
        "failed_breakout_reversal_short",
        exit_policy="two_r_half_atr_runner_v1",
        lookback=96,
        sweep_buffer=0.0015,
        rejection_buffer=0.0005,
        trend_ceiling=1.02,
        rsi_high=65,
        volume_min=1.4,
        atr_pct_min=0.002,
        atr_pct_max=0.025,
        stop_atr=1.0,
        max_hold=36,
    ),
    _candidate(
        "short_cycle_evidence_15m_liquidity_sweep_reclaim_long_v1",
        "15m 流动性扫低收回 ATR1.2",
        "15m",
        "long",
        "liquidity_sweep_reclaim_long",
        exit_policy="two_r_half_atr_runner_v1",
        lookback=64,
        sweep_buffer=0.002,
        reclaim_buffer=0.0005,
        trend_floor=0.96,
        rsi_oversold=40,
        rsi_recovery_min=38,
        volume_min=1.3,
        atr_pct_min=0.003,
        atr_pct_max=0.032,
        stop_atr=1.2,
        max_hold=24,
    ),
    _candidate(
        "short_cycle_evidence_15m_breakout_retest_continuation_long_v1",
        "15m 突破回踩确认 ATR1.2",
        "15m",
        "long",
        "breakout_retest_continuation_long",
        exit_policy="two_r_half_atr_runner_v1",
        lookback=64,
        breakout_buffer=0.0015,
        retest_tolerance=0.0045,
        reclaim_buffer=0.0005,
        trend_tolerance=1.0,
        rsi_min=46,
        rsi_max=72,
        breakout_volume_min=1.6,
        confirmation_volume_min=0.75,
        retest_volume_ratio_max=0.85,
        atr_pct_min=0.003,
        atr_pct_max=0.03,
        stop_atr=1.2,
        max_hold=24,
    ),
    _candidate(
        "short_cycle_evidence_15m_failed_breakout_reversal_short_v1",
        "15m 假突破反转 ATR1.2",
        "15m",
        "short",
        "failed_breakout_reversal_short",
        exit_policy="two_r_half_atr_runner_v1",
        lookback=64,
        sweep_buffer=0.002,
        rejection_buffer=0.0008,
        trend_ceiling=1.025,
        rsi_high=63,
        volume_min=1.3,
        atr_pct_min=0.003,
        atr_pct_max=0.032,
        stop_atr=1.2,
        max_hold=24,
    ),
)


def _validate_candidates(
    candidates: tuple[ShortCycleWorkflowCandidate, ...],
    *,
    expected_count: int,
) -> None:
    if len(candidates) != expected_count:
        raise ValueError(f"short_cycle_candidate_count_must_equal_{expected_count}")
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


_validate_candidates(_CANDIDATES, expected_count=10)
_validate_candidates(_REDESIGNED_CANDIDATES, expected_count=6)
_validate_candidates(_EVIDENCE_REDESIGNED_CANDIDATES, expected_count=6)


def short_cycle_workflow_candidates() -> tuple[ShortCycleWorkflowCandidate, ...]:
    return _CANDIDATES


def redesigned_short_cycle_workflow_candidates() -> tuple[
    ShortCycleWorkflowCandidate, ...
]:
    return _REDESIGNED_CANDIDATES


def evidence_redesigned_short_cycle_workflow_candidates() -> tuple[
    ShortCycleWorkflowCandidate, ...
]:
    return _EVIDENCE_REDESIGNED_CANDIDATES
