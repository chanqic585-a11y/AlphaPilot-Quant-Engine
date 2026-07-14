"""Build auditable 1h, 4h, and 1d research candidate packs.

Candidate count and promotion status are deliberately separate. A timeframe can
have five selected research candidates while none is eligible for promotion.
Locked evidence is reported but never participates in selection.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Mapping, Sequence


TIMEFRAMES = ("1h", "4h", "1d")
TARGET_R = 2.0


def deterministic_symbol_split(
    pairs: Sequence[str],
    *,
    holdback_share: float = 0.25,
) -> dict[str, tuple[str, ...]]:
    unique = sorted(set(str(pair) for pair in pairs))
    if len(unique) < 2:
        raise ValueError("long_horizon_symbol_split_requires_two_pairs")
    if not 0 < holdback_share < 1:
        raise ValueError("long_horizon_holdback_share_invalid")
    ranked = sorted(
        unique,
        key=lambda pair: (sha256(pair.encode("utf-8")).hexdigest(), pair),
    )
    holdback_count = max(1, min(len(ranked) - 1, round(len(ranked) * holdback_share)))
    holdback = tuple(sorted(ranked[:holdback_count]))
    development = tuple(sorted(set(ranked) - set(holdback)))
    return {"development": development, "holdback": holdback}


def _spec(
    candidate_id: str,
    display_name: str,
    timeframe: str,
    family: str,
    direction: str,
    *,
    correlation_group: str,
    evidence_lineage: str,
    **parameters: Any,
) -> dict[str, Any]:
    return {
        "candidateId": candidate_id,
        "displayName": display_name,
        "timeframe": timeframe,
        "family": family,
        "direction": direction,
        "targetR": TARGET_R,
        "correlationGroup": correlation_group,
        "evidenceLineage": evidence_lineage,
        "parameters": parameters,
        "researchOnly": True,
        "executionEnabled": False,
    }


def build_long_horizon_candidate_specs() -> tuple[dict[str, Any], ...]:
    """Return five transparent candidates per requested timeframe.

    The 1h set uses event windows and optional confirmation scoring instead of
    requiring every RSI/volume/candle check on one bar. The 4h set isolates the
    historically useful BTC bull recovery-reclaim regime. The 1d set preserves
    the five previously approved low-frequency definitions for re-audit.
    """

    one_hour = (
        _spec(
            "v13_27_17_1h_failed_breakout_window_v2",
            "1H 假突破事件窗口反转 ATR1.2",
            "1h",
            "windowed_failed_breakout_short",
            "short",
            correlation_group="1h_event_reversal",
            evidence_lineage="v13_7_40_short_rejection_plus_v13_27_17_event_window",
            event_window=3,
            minimum_optional_checks=2,
            stop_atr=1.2,
            max_hold=24,
        ),
        _spec(
            "v13_27_17_1h_failed_reclaim_window_v2",
            "1H 弱势回抽窗口失败 ATR1.2",
            "1h",
            "windowed_failed_reclaim_short",
            "short",
            correlation_group="1h_event_reversal",
            evidence_lineage="v13_7_40_short_rejection_plus_v13_27_17_event_window",
            event_window=3,
            minimum_optional_checks=2,
            stop_atr=1.2,
            max_hold=24,
        ),
        _spec(
            "v13_27_17_1h_breakout_retest_window_v2",
            "1H 突破回踩窗口确认 ATR1.2",
            "1h",
            "windowed_breakout_retest_long",
            "long",
            correlation_group="1h_event_continuation",
            evidence_lineage="v13_27_17_event_window",
            event_window=3,
            minimum_optional_checks=2,
            stop_atr=1.2,
            max_hold=24,
        ),
        _spec(
            "v13_27_17_1h_sweep_reclaim_window_v2",
            "1H 流动性扫低窗口收回 ATR1.2",
            "1h",
            "windowed_liquidity_sweep_reclaim_long",
            "long",
            correlation_group="1h_event_reversal_long",
            evidence_lineage="v13_27_17_event_window",
            event_window=4,
            minimum_optional_checks=2,
            stop_atr=1.2,
            max_hold=30,
        ),
        _spec(
            "v13_27_17_1h_trend_reclaim_window_v2",
            "1H 趋势回踩分步确认 ATR1.2",
            "1h",
            "windowed_trend_reclaim_long",
            "long",
            correlation_group="1h_event_continuation",
            evidence_lineage="v13_27_17_event_window",
            event_window=3,
            minimum_optional_checks=2,
            stop_atr=1.2,
            max_hold=24,
        ),
    )

    four_hour = tuple(
        _spec(
            candidate_id,
            display_name,
            "4h",
            "recovery_reclaim",
            "long",
            correlation_group="4h_btc_bull_recovery_reclaim",
            evidence_lineage="v13_7_20_factory_failure_attribution",
            btc_regimes=["bull"],
            atr_multiplier=atr,
            max_hold_bars=hold,
            min_volume_ratio=0.85,
            rsi_min=36,
            rsi_max=68,
            ema200_floor_multiplier=0.88,
        )
        for candidate_id, display_name, atr, hold in (
            ("v13_27_17_4h_bull_reclaim_atr15_h24", "4H 牛市回踩收回 ATR1.5 持有24", 1.5, 24),
            ("v13_27_17_4h_bull_reclaim_atr20_h24", "4H 牛市回踩收回 ATR2.0 持有24", 2.0, 24),
            ("v13_27_17_4h_bull_reclaim_atr18_h24", "4H 牛市回踩收回 ATR1.8 持有24", 1.8, 24),
            ("v13_27_17_4h_bull_reclaim_atr20_h36", "4H 牛市回踩收回 ATR2.0 持有36", 2.0, 36),
            ("v13_27_17_4h_bull_reclaim_atr20_h30", "4H 牛市回踩收回 ATR2.0 持有30", 2.0, 30),
        )
    )

    one_day = tuple(
        _spec(
            candidate_id,
            display_name,
            "1d",
            family,
            "long",
            correlation_group=correlation_group,
            evidence_lineage="v13_7_20_five_strategy_candidate_factory",
            legacy_candidate_id=legacy_id,
        )
        for candidate_id, legacy_id, display_name, family, correlation_group in (
            ("v13_27_17_1d_breakout_atr20", "lf_research_candidate_089", "1D 趋势突破确认 ATR2.0", "breakout", "1d_trend_breakout"),
            ("v13_27_17_1d_oversold_reclaim_atr12", "lf_research_candidate_117", "1D 震荡超卖收回 ATR1.2", "mean_reversion", "1d_oversold_reclaim"),
            ("v13_27_17_1d_oversold_reclaim_atr10", "lf_research_candidate_115", "1D 震荡超卖收回 ATR1.0", "mean_reversion", "1d_oversold_reclaim"),
            ("v13_27_17_1d_squeeze_breakout_atr20", "lf_research_candidate_090", "1D 趋势压缩突破 ATR2.0", "squeeze_breakout", "1d_squeeze_breakout"),
            ("v13_27_17_1d_broad_squeeze_breakout_atr20", "lf_research_candidate_108", "1D 广谱压缩突破 ATR2.0", "squeeze_breakout", "1d_squeeze_breakout"),
        )
    )
    return one_hour + four_hour + one_day


def classify_research_evidence(candidate: Mapping[str, Any]) -> dict[str, Any]:
    target_r = float(candidate.get("targetR") or 0)
    if target_r < TARGET_R:
        raise ValueError("long_horizon_candidate_target_r_below_two")

    checks = dict(candidate.get("selectionChecks") or {})
    failed = sorted(name for name, passed in checks.items() if not bool(passed))
    metrics = dict(candidate.get("metrics") or {})
    trades = int(metrics.get("tradeCount") or 0)
    profit_factor = float(metrics.get("profitFactor") or 0)
    if checks and not failed:
        tier = "research_eligible"
    elif trades > 0 and profit_factor > 1.0:
        tier = "shadow_only"
    else:
        tier = "rejected"
    return {
        **dict(candidate),
        "selectionTier": tier,
        "failedSelectionChecks": failed,
        "lockedOrHoldoutUsedForSelection": False,
    }


def classify_event_window_prescreen_result(
    candidate: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Translate direct event-window evidence without borrowing lineage metrics."""

    target_r = float(candidate.get("targetR") or 0)
    if target_r < TARGET_R:
        raise ValueError("long_horizon_candidate_target_r_below_two")
    segments = dict(result.get("segmentMetrics") or {})
    required = ("derivationTrain", "derivationValidation", "symbolHoldback")
    if any(name not in segments for name in required):
        raise ValueError("long_horizon_direct_event_segments_missing")
    trade_count = sum(int(segments[name].get("tradeCount") or 0) for name in required)
    profit_factor = min(
        float(segments[name].get("profitFactor") or 0) for name in required
    )
    expectancy_r = min(
        float(segments[name].get("expectancyR") or 0) for name in required
    )
    failed = list(result.get("rejectionReasons") or [])
    if bool(result.get("eligible")) and not failed:
        tier = "research_eligible"
    elif trade_count > 0 and profit_factor > 1.0 and expectancy_r > 0:
        tier = "shadow_only"
    else:
        tier = "rejected"
    return {
        **dict(candidate),
        "metrics": {
            "tradeCount": trade_count,
            "profitFactor": round(profit_factor, 8),
            "expectancyR": round(expectancy_r, 8),
        },
        "segmentMetrics": segments,
        "selectionTier": tier,
        "failedSelectionChecks": failed,
        "selectionScore": round(expectancy_r * 100 + profit_factor, 8),
        "directCandidateBacktestCompleted": True,
        "metricsProvenance": "direct_event_window_prescreen",
        "lockedOrHoldoutUsedForSelection": False,
    }


def select_timeframe_pack(
    candidates: Sequence[Mapping[str, Any]],
    *,
    timeframe: str,
    limit: int = 5,
) -> tuple[dict[str, Any], ...]:
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"long_horizon_timeframe_not_supported:{timeframe}")
    rows = [dict(item) for item in candidates if item.get("timeframe") == timeframe]
    tier_rank = {"research_eligible": 2, "shadow_only": 1, "rejected": 0}
    rows.sort(
        key=lambda item: (
            tier_rank.get(str(item.get("selectionTier")), -1),
            float(item.get("selectionScore") or 0),
            str(item.get("candidateId") or ""),
        ),
        reverse=True,
    )
    return tuple(rows[:limit])


def build_long_horizon_report(
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    packs = {
        timeframe: list(
            select_timeframe_pack(candidates, timeframe=timeframe, limit=5)
        )
        for timeframe in TIMEFRAMES
    }
    incomplete = [timeframe for timeframe, rows in packs.items() if len(rows) != 5]
    if incomplete:
        raise ValueError(
            "long_horizon_candidate_pack_incomplete:" + ",".join(incomplete)
        )
    eligible = {
        timeframe: sum(
            item.get("selectionTier") == "research_eligible" for item in rows
        )
        for timeframe, rows in packs.items()
    }
    shadow = {
        timeframe: sum(item.get("selectionTier") == "shadow_only" for item in rows)
        for timeframe, rows in packs.items()
    }
    rejected = {
        timeframe: sum(item.get("selectionTier") == "rejected" for item in rows)
        for timeframe, rows in packs.items()
    }
    return {
        "schemaVersion": "long_horizon_candidate_pack_report_v1",
        "status": "completed",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "objective": "Select five auditable research candidates each for 1h, 4h, and 1d without forcing promotion.",
        "targetR": TARGET_R,
        "selectionBoundary": "development_and_declared_validation_checks_only",
        "lockedOrHoldoutUsedForSelection": False,
        "candidatePacks": packs,
        "summary": {
            "selectedCandidateCount": sum(len(rows) for rows in packs.values()),
            "selectedByTimeframe": {
                timeframe: len(rows) for timeframe, rows in packs.items()
            },
            "researchEligibleByTimeframe": eligible,
            "shadowOnlyByTimeframe": shadow,
            "rejectedByTimeframe": rejected,
        },
        "safetyBoundary": {
            "researchOnly": True,
            "executionEnabled": False,
            "demoReleaseCreated": False,
            "liveReleaseCreated": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "apiKeyStored": False,
        },
    }
