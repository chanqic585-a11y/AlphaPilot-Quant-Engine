"""Evidence-informed 5m and 15m event-window research candidates."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Any

from .workflow_candidates import ShortCycleWorkflowCandidate


FAILURE_LESSONS = (
    "avoid_bar_by_bar_overtrading",
    "require_positive_cost_adjusted_development_expectancy",
    "separate_setup_and_confirmation_across_closed_candles",
    "preserve_btc_shock_and_volatility_guards",
)


def _candidate(
    key: str,
    name: str,
    timeframe: str,
    direction: str,
    family: str,
    *,
    variant: str,
    selection_method: str = "development_prescreen_v1",
    prescreen_status: str | None = None,
    development_factor_attribution: dict[str, Any] | None = None,
    **parameters: Any,
) -> ShortCycleWorkflowCandidate:
    metadata: dict[str, Any] = {
        "schemaVersion": "event_window_candidate_metadata_v1",
        "candidatePack": (
            "V13.27.17" if timeframe in {"1h", "4h", "1d"} else "V13.27.16"
        ),
        "selectionMethod": selection_method,
        "variant": variant,
        "archivedFailureLessons": list(FAILURE_LESSONS),
        "nearMissPolicy": "shadow_only_no_execution",
        "formalPromotionEvidence": False,
        "lockedOrHoldoutUsedForSelection": False,
    }
    if prescreen_status is not None:
        metadata["prescreenStatus"] = prescreen_status
    if development_factor_attribution is not None:
        metadata["developmentFactorAttribution"] = development_factor_attribution
    return ShortCycleWorkflowCandidate(
        familyKey=key,
        displayName=name,
        timeframe=timeframe,
        direction=direction,
        signalFamily=family,
        parameters=parameters,
        exitPolicy="two_r_half_atr_runner_v1",
        researchMetadata=metadata,
    )


def _pool_for_timeframe(timeframe: str) -> tuple[ShortCycleWorkflowCandidate, ...]:
    if timeframe == "5m":
        stop_atr, max_hold = 1.0, 36
        lookback, slope = 96, 8
        atr_min, atr_max = 0.0018, 0.022
        label = "5m"
    elif timeframe == "15m":
        stop_atr, max_hold = 1.2, 24
        lookback, slope = 64, 6
        atr_min, atr_max = 0.0025, 0.030
        label = "15m"
    elif timeframe == "1h":
        stop_atr, max_hold = 1.2, 24
        lookback, slope = 48, 6
        atr_min, atr_max = 0.003, 0.080
        label = "1H"
    elif timeframe == "4h":
        stop_atr, max_hold = 1.5, 30
        lookback, slope = 36, 4
        atr_min, atr_max = 0.005, 0.150
        label = "4H"
    elif timeframe == "1d":
        stop_atr, max_hold = 1.8, 20
        lookback, slope = 30, 3
        atr_min, atr_max = 0.008, 0.250
        label = "1D"
    else:
        raise ValueError(f"event_window_timeframe_not_supported:{timeframe}")

    common = {
        "stop_atr": stop_atr,
        "max_hold": max_hold,
        "atr_pct_min": atr_min,
        "atr_pct_max": atr_max,
    }
    if timeframe in {"1h", "4h", "1d"}:
        common.update(
            {
                "minimum_optional_checks": 3,
                "btc_shock_threshold": {
                    "1h": 0.03,
                    "4h": 0.06,
                    "1d": 0.12,
                }[timeframe],
            }
        )
    prefix = f"short_cycle_event_{timeframe}"
    return (
        _candidate(
            f"{prefix}_trend_reclaim_balanced_v1",
            f"{label} 趋势回踩分步确认 ATR{stop_atr:.1f}",
            timeframe,
            "long",
            "windowed_trend_reclaim_long",
            variant="balanced",
            event_window=3,
            pullback_tolerance=0.004 if timeframe == "5m" else 0.006,
            reclaim_buffer=0.0004,
            trend_tolerance=0.998,
            ema_slope_lookback=slope,
            rsi_min=44,
            rsi_max=68,
            volume_min=0.9,
            volume_max=3.5,
            **common,
        ),
        _candidate(
            f"{prefix}_trend_reclaim_selective_v1",
            f"{label} 趋势回踩动量确认 ATR{stop_atr:.1f}",
            timeframe,
            "long",
            "windowed_trend_reclaim_long",
            variant="selective",
            event_window=2,
            pullback_tolerance=0.003 if timeframe == "5m" else 0.005,
            reclaim_buffer=0.001,
            trend_tolerance=1.0,
            ema_slope_lookback=slope,
            rsi_min=48,
            rsi_max=65,
            volume_min=1.1,
            volume_max=3.0,
            **common,
        ),
        _candidate(
            f"{prefix}_breakout_retest_balanced_v1",
            f"{label} 突破回踩窗口确认 ATR{stop_atr:.1f}",
            timeframe,
            "long",
            "windowed_breakout_retest_long",
            variant="balanced",
            event_window=3,
            lookback=lookback,
            breakout_buffer=0.0005,
            retest_tolerance=0.004 if timeframe == "5m" else 0.006,
            reclaim_buffer=0.0002,
            trend_tolerance=0.998,
            rsi_min=48,
            rsi_max=70,
            breakout_volume_min=1.35,
            confirmation_volume_min=0.75,
            confirmation_volume_max=3.5,
            **common,
        ),
        _candidate(
            f"{prefix}_breakout_retest_selective_v1",
            f"{label} 压缩突破回踩确认 ATR{stop_atr:.1f}",
            timeframe,
            "long",
            "windowed_breakout_retest_long",
            variant="selective",
            event_window=2,
            lookback=lookback,
            breakout_buffer=0.001,
            retest_tolerance=0.003 if timeframe == "5m" else 0.005,
            reclaim_buffer=0.0005,
            trend_tolerance=1.0,
            rsi_min=50,
            rsi_max=68,
            breakout_volume_min=1.6,
            confirmation_volume_min=0.8,
            confirmation_volume_max=3.0,
            **common,
        ),
        _candidate(
            f"{prefix}_sweep_reclaim_balanced_v1",
            f"{label} 流动性扫低窗口收回 ATR{stop_atr:.1f}",
            timeframe,
            "long",
            "windowed_liquidity_sweep_reclaim_long",
            variant="balanced",
            event_window=3,
            lookback=lookback,
            sweep_buffer=0.001,
            reclaim_buffer=0.0003,
            trend_floor=0.97,
            rsi_oversold=40,
            rsi_recovery_min=38,
            volume_min=1.0,
            volume_max=4.0,
            **common,
        ),
        _candidate(
            f"{prefix}_sweep_reclaim_selective_v1",
            f"{label} 流动性扫低反转确认 ATR{stop_atr:.1f}",
            timeframe,
            "long",
            "windowed_liquidity_sweep_reclaim_long",
            variant="selective",
            event_window=2,
            lookback=lookback,
            sweep_buffer=0.0018,
            reclaim_buffer=0.0008,
            trend_floor=0.985,
            rsi_oversold=35,
            rsi_recovery_min=40,
            volume_min=1.25,
            volume_max=3.5,
            **common,
        ),
        _candidate(
            f"{prefix}_failed_breakout_balanced_v1",
            f"{label} 假突破窗口反转 ATR{stop_atr:.1f}",
            timeframe,
            "short",
            "windowed_failed_breakout_short",
            variant="balanced",
            event_window=3,
            lookback=lookback,
            sweep_buffer=0.001,
            rejection_buffer=0.0003,
            trend_ceiling=1.02,
            rsi_high=62,
            rsi_reversal_max=64,
            volume_min=1.0,
            volume_max=4.0,
            **common,
        ),
        _candidate(
            f"{prefix}_failed_breakout_selective_v1",
            f"{label} 放量假突破反转 ATR{stop_atr:.1f}",
            timeframe,
            "short",
            "windowed_failed_breakout_short",
            variant="selective",
            event_window=2,
            lookback=lookback,
            sweep_buffer=0.0018,
            rejection_buffer=0.0008,
            trend_ceiling=1.01,
            rsi_high=68,
            rsi_reversal_max=62,
            volume_min=1.25,
            volume_max=3.5,
            **common,
        ),
        _candidate(
            f"{prefix}_failed_reclaim_balanced_v1",
            f"{label} 弱势回抽窗口失败 ATR{stop_atr:.1f}",
            timeframe,
            "short",
            "windowed_failed_reclaim_short",
            variant="balanced",
            event_window=3,
            reclaim_tolerance=0.005,
            rejection_buffer=0.0005,
            trend_tolerance=1.002,
            ema_slope_lookback=slope,
            rsi_min=34,
            rsi_max=58,
            volume_min=0.9,
            volume_max=3.5,
            **common,
        ),
        _candidate(
            f"{prefix}_failed_reclaim_selective_v1",
            f"{label} 弱势回抽动量失败 ATR{stop_atr:.1f}",
            timeframe,
            "short",
            "windowed_failed_reclaim_short",
            variant="selective",
            event_window=2,
            reclaim_tolerance=0.003,
            rejection_buffer=0.001,
            trend_tolerance=1.0,
            ema_slope_lookback=slope,
            rsi_min=38,
            rsi_max=54,
            volume_min=1.1,
            volume_max=3.0,
            **common,
        ),
    )


_BASE_POOL = _pool_for_timeframe("5m") + _pool_for_timeframe("15m")
_LONG_HORIZON_POOL = (
    _pool_for_timeframe("1h")
    + _pool_for_timeframe("4h")
    + _pool_for_timeframe("1d")
)


def _learned_from(
    base_key: str,
    key: str,
    name: str,
    *,
    attribution: dict[str, Any],
    **overrides: Any,
) -> ShortCycleWorkflowCandidate:
    base = next(item for item in _BASE_POOL if item.familyKey == base_key)
    parameters = {**base.parameters, **overrides}
    return _candidate(
        key,
        name,
        base.timeframe,
        base.direction,
        base.signalFamily,
        variant="learned_v1",
        selection_method="failure_attribution_temporal_symbol_holdback_v1",
        prescreen_status="expanded_validation_pending",
        development_factor_attribution=attribution,
        **parameters,
    )


def _attribution(
    *,
    factors: dict[str, float],
    train: tuple[int, float, float],
    validation: tuple[int, float, float],
) -> dict[str, Any]:
    return {
        "schemaVersion": "development_factor_attribution_v1",
        "derivationSymbols": [
            "BTC-USDT-SWAP",
            "ETH-USDT-SWAP",
            "SOL-USDT-SWAP",
            "ADA-USDT-SWAP",
            "AAVE-USDT-SWAP",
            "AVAX-USDT-SWAP",
        ],
        "trainWindow": "2022-01-01/2024-01-01",
        "temporalValidationWindow": "2024-01-01/2025-01-01",
        "transparentFactors": factors,
        "train": {
            "tradeCount": train[0],
            "averageNetR": train[1],
            "profitFactor": train[2],
        },
        "temporalValidation": {
            "tradeCount": validation[0],
            "averageNetR": validation[1],
            "profitFactor": validation[2],
        },
        "lockedOrHoldoutUsedForSelection": False,
    }


_LEARNED_POOL = (
    _learned_from(
        "short_cycle_event_5m_trend_reclaim_balanced_v1",
        "short_cycle_event_5m_trend_reclaim_learned_v1",
        "5m 趋势回踩事件确认 学习版 ATR2.2",
        attribution=_attribution(
            factors={"atr_pct_min": 0.005814531, "aligned_slope20_max": -0.000337731},
            train=(88, 0.07510, 1.114),
            validation=(57, 0.04145, 1.062),
        ),
        stop_atr=2.2,
        max_hold=180,
        atr_pct_min=0.005814531,
        factor_lookback=12,
        aligned_slope20_max=-0.000337731,
    ),
    _learned_from(
        "short_cycle_event_5m_breakout_retest_selective_v1",
        "short_cycle_event_5m_breakout_retest_learned_v1",
        "5m 突破回踩环境确认 学习版 ATR1.8",
        attribution=_attribution(
            factors={"btc_aligned_max": 0.002634585, "aligned_trend50_200_min": 0.013361868},
            train=(65, 0.15914, 1.243),
            validation=(50, 0.07236, 1.105),
        ),
        stop_atr=1.8,
        max_hold=120,
        btc_aligned_max=0.002634585,
        aligned_trend50_200_min=0.013361868,
    ),
    _learned_from(
        "short_cycle_event_5m_sweep_reclaim_balanced_v1",
        "short_cycle_event_5m_sweep_reclaim_learned_v1",
        "5m 扫低收回环境确认 学习版 ATR2.2",
        attribution=_attribution(
            factors={"atr_pct_min": 0.006765467, "btc_aligned_min": 0.001063775},
            train=(195, 0.03566, 1.061),
            validation=(128, 0.03385, 1.061),
        ),
        stop_atr=2.2,
        max_hold=72,
        atr_pct_min=0.006765467,
        btc_aligned_min=0.001063775,
    ),
    _learned_from(
        "short_cycle_event_5m_failed_breakout_balanced_v1",
        "short_cycle_event_5m_failed_breakout_learned_v1",
        "5m 假突破反转环境确认 学习版 ATR2.2",
        attribution=_attribution(
            factors={"btc_aligned_min": 0.005750827, "aligned_return_max": -0.008592567},
            train=(73, 0.10741, 1.163),
            validation=(38, 0.10614, 1.163),
        ),
        stop_atr=2.2,
        max_hold=180,
        factor_lookback=12,
        btc_aligned_min=0.005750827,
        aligned_return_max=-0.008592567,
    ),
    _learned_from(
        "short_cycle_event_5m_failed_reclaim_selective_v1",
        "short_cycle_event_5m_failed_reclaim_learned_v1",
        "5m 弱势回抽结构确认 学习版 ATR2.2",
        attribution=_attribution(
            factors={"aligned_trend50_200_min": 0.020717401, "aligned_trend20_50_min": 0.002766310},
            train=(196, 0.11853, 1.183),
            validation=(99, 0.04216, 1.062),
        ),
        stop_atr=2.2,
        max_hold=120,
        aligned_trend50_200_min=0.020717401,
        aligned_trend20_50_min=0.002766310,
    ),
    _learned_from(
        "short_cycle_event_15m_trend_reclaim_balanced_v1",
        "short_cycle_event_15m_trend_reclaim_regime_learned_v1",
        "15m 趋势回踩高波确认 学习版 ATR1.2",
        attribution=_attribution(
            factors={"atr_pct_min": 0.009852181, "aligned_slope20_min": 0.006657844},
            train=(132, 0.12350, 1.197),
            validation=(82, 0.13680, 1.212),
        ),
        atr_pct_min=0.009852181,
        factor_lookback=12,
        aligned_slope20_min=0.006657844,
    ),
    _learned_from(
        "short_cycle_event_15m_trend_reclaim_selective_v1",
        "short_cycle_event_15m_trend_reclaim_momentum_learned_v1",
        "15m 趋势回踩动量环境 学习版 ATR1.2",
        attribution=_attribution(
            factors={"aligned_trend20_50_min": 0.010147123, "aligned_return_min": 0.008237167},
            train=(62, 0.22710, 1.382),
            validation=(40, 0.37780, 1.674),
        ),
        factor_lookback=12,
        aligned_trend20_50_min=0.010147123,
        aligned_return_min=0.008237167,
    ),
    _learned_from(
        "short_cycle_event_15m_failed_breakout_balanced_v1",
        "short_cycle_event_15m_failed_breakout_regime_learned_v1",
        "15m 假突破逆势衰竭 学习版 ATR1.2",
        attribution=_attribution(
            factors={"aligned_slope20_max": -0.014001055, "aligned_trend50_200_min": 0.005937076},
            train=(93, 0.02420, 1.037),
            validation=(59, 0.00663, 1.010),
        ),
        factor_lookback=12,
        aligned_slope20_max=-0.014001055,
        aligned_trend50_200_min=0.005937076,
    ),
    _learned_from(
        "short_cycle_event_15m_failed_reclaim_balanced_v1",
        "short_cycle_event_15m_failed_reclaim_pullback_learned_v1",
        "15m 弱势回抽衰竭 学习版 ATR1.2",
        attribution=_attribution(
            factors={"aligned_trend50_200_min": 0.030333068, "aligned_slope20_max": -0.001054939},
            train=(64, 0.04836, 1.070),
            validation=(46, 0.15208, 1.236),
        ),
        factor_lookback=12,
        aligned_trend50_200_min=0.030333068,
        aligned_slope20_max=-0.001054939,
    ),
    _learned_from(
        "short_cycle_event_15m_failed_reclaim_selective_v1",
        "short_cycle_event_15m_failed_reclaim_range_learned_v1",
        "15m 弱势回抽区间衰竭 学习版 ATR1.2",
        attribution=_attribution(
            factors={"aligned_trend50_200_max": 0.002845908, "atr_pct_min": 0.003176349},
            train=(84, 0.06128, 1.093),
            validation=(70, 0.10046, 1.152),
        ),
        atr_pct_min=0.003176349,
        aligned_trend50_200_max=0.002845908,
    ),
)


def _factor_segment(
    trade_count: int,
    expectancy_r: float,
    profit_factor: float,
    largest_pair_share: float,
) -> dict[str, float | int]:
    return {
        "tradeCount": trade_count,
        "expectancyR": expectancy_r,
        "profitFactor": profit_factor,
        "largestPairShare": largest_pair_share,
    }


def _factor_successor_from(
    base_key: str,
    key: str,
    name: str,
    *,
    factor_guards: dict[str, float],
    train: dict[str, float | int],
    validation: dict[str, float | int],
    holdback: dict[str, float | int],
) -> ShortCycleWorkflowCandidate:
    base = next(item for item in _LEARNED_POOL if item.familyKey == base_key)
    attribution = {
        "schemaVersion": "robust_factor_successor_attribution_v1",
        "sourceArtifact": "reports/v13_27_17_event_window_factor_discovery_expanded.json",
        "selectionBoundary": "development_temporal_validation_and_symbol_holdback_only",
        "transparentFactors": dict(factor_guards),
        "derivationTrain": dict(train),
        "derivationValidation": dict(validation),
        "symbolHoldback": dict(holdback),
        "lockedOrHoldoutUsedForSelection": False,
    }
    return _candidate(
        key,
        name,
        base.timeframe,
        base.direction,
        base.signalFamily,
        variant="factor_successor_v2",
        selection_method="robust_factor_temporal_symbol_holdback_v1",
        prescreen_status="robust_factor_successor_pending_recheck",
        development_factor_attribution=attribution,
        **{**base.parameters, **factor_guards},
    )


_FACTOR_SUCCESSOR_POOL = (
    _factor_successor_from(
        "short_cycle_event_15m_trend_reclaim_regime_learned_v1",
        "short_cycle_event_15m_trend_reclaim_factor_v2",
        "15m 趋势回踩双趋势确认 因子后继 ATR1.2",
        factor_guards={
            "aligned_slope20_min": 0.011184064132,
            "aligned_trend20_50_min": 0.00995571286,
        },
        train=_factor_segment(42, 0.2073139, 1.34721937, 0.35714286),
        validation=_factor_segment(30, 0.2080619, 1.33539628, 0.4),
        holdback=_factor_segment(60, 0.12445678, 1.20457862, 0.26666667),
    ),
    _factor_successor_from(
        "short_cycle_event_15m_trend_reclaim_momentum_learned_v1",
        "short_cycle_event_15m_trend_reclaim_btc_factor_v2",
        "15m 趋势回踩波动环境确认 因子后继 ATR1.2",
        factor_guards={
            "atr_pct_min": 0.008246231491,
            "btc_trend50_200_min": 0.006198866973,
        },
        train=_factor_segment(37, 0.43298632, 1.85393293, 0.2972973),
        validation=_factor_segment(21, 0.45762681, 1.86195794, 0.28571429),
        holdback=_factor_segment(37, 0.03006043, 1.04384523, 0.35135135),
    ),
    _factor_successor_from(
        "short_cycle_event_15m_failed_breakout_regime_learned_v1",
        "short_cycle_event_15m_failed_breakout_factor_v2",
        "15m 假突破弱趋势反转 因子后继 ATR1.2",
        factor_guards={
            "aligned_trend20_50_max": -0.006267491756,
            "aligned_slope20_min": -0.022922970969,
        },
        train=_factor_segment(37, 0.38506146, 1.73433625, 0.37837838),
        validation=_factor_segment(20, 0.2681257, 1.47850238, 0.35),
        holdback=_factor_segment(51, 0.25429594, 1.42116215, 0.31372549),
    ),
    _factor_successor_from(
        "short_cycle_event_15m_failed_reclaim_pullback_learned_v1",
        "short_cycle_event_15m_failed_reclaim_factor_v2",
        "15m 弱势回抽市场斜率确认 因子后继 ATR1.2",
        factor_guards={
            "btc_slope20_12_max": -0.000555627867,
            "aligned_trend50_200_max": 0.051430504647,
        },
        train=_factor_segment(33, 0.25848094, 1.42521849, 0.24242424),
        validation=_factor_segment(28, 0.33350611, 1.57213394, 0.32142857),
        holdback=_factor_segment(40, 0.2784038, 1.46560104, 0.35),
    ),
    _candidate(
        "short_cycle_event_15m_failed_reclaim_range_shadow_v2",
        "15m 弱势回抽区间衰竭 影子候选 ATR1.2",
        "15m",
        "short",
        "windowed_failed_reclaim_short",
        variant="factor_shadow_v2",
        selection_method="robust_factor_temporal_symbol_holdback_v1",
        prescreen_status="no_robust_factor_guard_shadow_only",
        development_factor_attribution={
            "schemaVersion": "robust_factor_successor_attribution_v1",
            "sourceArtifact": "reports/v13_27_17_event_window_factor_discovery_expanded.json",
            "robustFactorGuardCount": 0,
            "lockedOrHoldoutUsedForSelection": False,
        },
        **next(
            item.parameters
            for item in _LEARNED_POOL
            if item.familyKey
            == "short_cycle_event_15m_failed_reclaim_range_learned_v1"
        ),
    ),
)


def _one_hour_base(signal_family: str) -> ShortCycleWorkflowCandidate:
    return next(
        item
        for item in _LONG_HORIZON_POOL
        if item.timeframe == "1h"
        and item.signalFamily == signal_family
        and item.researchMetadata
        and item.researchMetadata.get("variant") == "balanced"
    )


def _one_hour_successor(
    signal_family: str,
    key: str,
    name: str,
    *,
    factor_guards: dict[str, float] | None = None,
    train: dict[str, float | int] | None = None,
    validation: dict[str, float | int] | None = None,
    holdback: dict[str, float | int] | None = None,
) -> ShortCycleWorkflowCandidate:
    base = _one_hour_base(signal_family)
    robust = factor_guards is not None
    attribution: dict[str, Any] = {
        "schemaVersion": "robust_factor_successor_attribution_v1",
        "sourceArtifact": "reports/v13_27_17_long_horizon_1h_factor_discovery.json",
        "selectionBoundary": "development_temporal_validation_and_symbol_holdback_only",
        "robustFactorGuardCount": 1 if robust else 0,
        "lockedOrHoldoutUsedForSelection": False,
    }
    if robust:
        attribution.update(
            {
                "transparentFactors": dict(factor_guards or {}),
                "derivationTrain": dict(train or {}),
                "derivationValidation": dict(validation or {}),
                "symbolHoldback": dict(holdback or {}),
            }
        )
    return _candidate(
        key,
        name,
        "1h",
        base.direction,
        base.signalFamily,
        variant="factor_successor_v2" if robust else "factor_shadow_v2",
        selection_method="robust_factor_temporal_symbol_holdback_v1",
        prescreen_status=(
            "robust_factor_successor_pending_recheck"
            if robust
            else "no_robust_factor_guard_shadow_only"
        ),
        development_factor_attribution=attribution,
        **{
            **base.parameters,
            "minimum_optional_checks": 2,
            **(factor_guards or {}),
        },
    )


_ONE_HOUR_FACTOR_SUCCESSOR_POOL = (
    _one_hour_successor(
        "windowed_breakout_retest_long",
        "short_cycle_event_1h_breakout_retest_btc_factor_v2",
        "1H 突破回踩 BTC 顺势确认 因子后继 ATR1.2",
        factor_guards={"btc_aligned_min": 0.019947838608},
        train=_factor_segment(198, 0.12623156, 1.19775138, 0.20707071),
        validation=_factor_segment(116, 0.25650314, 1.45156884, 0.27586207),
        holdback=_factor_segment(144, 0.12493283, 1.19816771, 0.30555556),
    ),
    _one_hour_successor(
        "windowed_liquidity_sweep_reclaim_long",
        "short_cycle_event_1h_sweep_reclaim_factor_v2",
        "1H 深弱势扫低收回 因子后继 ATR1.2",
        factor_guards={
            "aligned_trend50_200_max": -0.038470501732,
            "aligned_return_max": -0.033335144886,
        },
        train=_factor_segment(106, 0.29875696, 1.54827293, 0.22641509),
        validation=_factor_segment(41, 0.59728337, 2.34725346, 0.34146341),
        holdback=_factor_segment(97, 0.23390462, 1.42009338, 0.29896907),
    ),
    _one_hour_successor(
        "windowed_failed_breakout_short",
        "short_cycle_event_1h_failed_breakout_shadow_v2",
        "1H 假突破事件窗口反转 影子候选 ATR1.2",
    ),
    _one_hour_successor(
        "windowed_failed_reclaim_short",
        "short_cycle_event_1h_failed_reclaim_shadow_v2",
        "1H 弱势回抽窗口失败 影子候选 ATR1.2",
    ),
    _one_hour_successor(
        "windowed_trend_reclaim_long",
        "short_cycle_event_1h_trend_reclaim_shadow_v2",
        "1H 趋势回踩分步确认 影子候选 ATR1.2",
    ),
)

_POOL = _BASE_POOL + _LEARNED_POOL

# These keys are replaced only after a deterministic development pre-screen.
# The initial set deliberately covers all five structures once per timeframe.
_SELECTED_KEYS = tuple(
    f"short_cycle_event_{timeframe}_{suffix}_v1"
    for timeframe in ("5m", "15m")
    for suffix in (
        "trend_reclaim_balanced",
        "breakout_retest_balanced",
        "sweep_reclaim_balanced",
        "failed_breakout_balanced",
        "failed_reclaim_balanced",
    )
)


def event_window_candidate_pool() -> tuple[ShortCycleWorkflowCandidate, ...]:
    return _POOL


def event_window_learned_candidate_pool() -> tuple[ShortCycleWorkflowCandidate, ...]:
    return _LEARNED_POOL


def event_window_factor_successor_candidate_pool() -> tuple[
    ShortCycleWorkflowCandidate, ...
]:
    return _FACTOR_SUCCESSOR_POOL


def one_hour_factor_successor_candidate_pool() -> tuple[
    ShortCycleWorkflowCandidate, ...
]:
    return _ONE_HOUR_FACTOR_SUCCESSOR_POOL


_RESEARCH_ELIGIBLE_WORKFLOW_KEYS = (
    "short_cycle_event_5m_trend_reclaim_learned_v1",
    "short_cycle_event_5m_failed_breakout_learned_v1",
    "short_cycle_event_15m_trend_reclaim_factor_v2",
    "short_cycle_event_15m_trend_reclaim_btc_factor_v2",
    "short_cycle_event_15m_failed_breakout_factor_v2",
    "short_cycle_event_15m_failed_reclaim_factor_v2",
    "short_cycle_event_1h_sweep_reclaim_factor_v2",
)


def research_eligible_event_window_workflow_candidates() -> tuple[
    ShortCycleWorkflowCandidate, ...
]:
    """Return only directly pre-screened candidates with an executable policy."""

    source_by_timeframe = {
        "5m": "reports/v13_27_16_event_window_prescreen.json",
        "15m": "reports/v13_27_17_event_window_factor_successor_prescreen.json",
        "1h": "reports/v13_27_17_long_horizon_1h_factor_successor_prescreen.json",
    }
    candidates = (
        *_LEARNED_POOL,
        *_FACTOR_SUCCESSOR_POOL,
        *_ONE_HOUR_FACTOR_SUCCESSOR_POOL,
    )
    by_key = {item.familyKey: item for item in candidates}
    selected: list[ShortCycleWorkflowCandidate] = []
    for key in _RESEARCH_ELIGIBLE_WORKFLOW_KEYS:
        item = by_key[key]
        metadata = dict(item.researchMetadata or {})
        metadata.update(
            {
                "candidatePack": "V13.27.17",
                "prescreenStatus": "research_eligible_direct_prescreen",
                "directPrescreenArtifact": source_by_timeframe[item.timeframe],
                "formalPromotionEvidence": False,
                "lockedOrHoldoutUsedForSelection": False,
            }
        )
        selected.append(replace(item, researchMetadata=metadata))
    result = tuple(selected)
    if Counter(item.timeframe for item in result) != {"5m": 2, "15m": 4, "1h": 1}:
        raise ValueError("research_eligible_event_window_pack_shape_invalid")
    return result


def long_horizon_event_candidate_pool() -> tuple[
    ShortCycleWorkflowCandidate, ...
]:
    return _LONG_HORIZON_POOL


def event_window_short_cycle_workflow_candidates() -> tuple[
    ShortCycleWorkflowCandidate, ...
]:
    by_key = {item.familyKey: item for item in _POOL}
    selected = tuple(by_key[key] for key in _SELECTED_KEYS)
    if Counter(item.timeframe for item in selected) != {"5m": 5, "15m": 5}:
        raise ValueError("event_window_selected_pack_must_contain_five_per_timeframe")
    return selected
