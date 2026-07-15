from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .models import CandidateVersion


_FAMILY_CONTRACTS: dict[str, tuple[str, str]] = {
    "short_cycle_event_1h_sweep_reclaim_factor_v2": (
        "A",
        "1H 深弱势扫低收回，因子后继 ATR1.2",
    ),
    "event_1d_breakout_retest_atr20_v1": ("A", "1D 趋势突破回踩 ATR2.0"),
    "event_1d_squeeze_breakout_atr20_v1": ("A", "1D 趋势压缩释放 ATR2.0"),
    "event_1d_broad_squeeze_breakout_atr20_v1": (
        "A",
        "1D 广谱压缩释放 ATR2.0",
    ),
    "short_cycle_event_1h_breakout_retest_btc_factor_v2": (
        "B",
        "1H 突破回踩 BTC 顺势确认，因子后继 ATR1.2",
    ),
    "event_1d_oversold_sweep_reclaim_atr12_v1": (
        "C",
        "1D 超卖扫低收回 ATR1.2 影子",
    ),
    "short_cycle_event_15m_failed_breakout_factor_v2": (
        "C",
        "15m 假突破弱趋势反转，因子后继 ATR1.2",
    ),
}


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def discover_candidates(
    failure_attributions: Iterable[Mapping[str, Any]],
) -> list[CandidateVersion]:
    """Discover registered risk-path failures without inventing candidates."""

    candidates: list[CandidateVersion] = []
    for row in failure_attributions:
        if row.get("primaryFailureType") != "risk_model_failure":
            continue
        family = str(row.get("strategyFamily") or "")
        if not family:
            continue
        tier, display_label = _FAMILY_CONTRACTS.get(
            family,
            ("B", str(row.get("strategyName") or family)),
        )
        signal_layer = row.get("signalLayer") or {}
        evidence = row.get("evidenceBasis") or {}
        profit_factor = _optional_float(signal_layer.get("profitFactor"))
        average_net_r = _optional_float(signal_layer.get("averageNetR"))
        requires_prefilter = tier == "C"
        prefilter_passed = bool(
            requires_prefilter
            and profit_factor is not None
            and average_net_r is not None
            and profit_factor >= 1.05
            and average_net_r >= 0.02
        )
        strategy_version_id = str(
            row.get("strategyVersionId") or row.get("strategyId") or ""
        )
        if not strategy_version_id:
            continue
        candidates.append(
            CandidateVersion(
                strategy_version_id=strategy_version_id,
                strategy_family=family,
                strategy_name=str(row.get("strategyName") or family),
                display_label_zh=display_label,
                timeframe=str(row.get("timeframe") or "unknown"),
                tier=tier,
                historical_profit_factor=profit_factor,
                historical_average_net_r=average_net_r,
                historical_trade_count=_optional_int(evidence.get("tradeCount")),
                requires_prefilter=requires_prefilter,
                historical_prefilter_passed=prefilter_passed,
                source_definition_hash=(
                    str(row["strategyDefinitionHash"])
                    if row.get("strategyDefinitionHash")
                    else None
                ),
                source_signal_hash=(
                    str(row["signalDefinitionHash"])
                    if row.get("signalDefinitionHash")
                    else None
                ),
                parent_strategy_version_id=(
                    str(row["parentStrategyVersionId"])
                    if row.get("parentStrategyVersionId")
                    else None
                ),
                auto_optimization_generation=_optional_int(
                    row.get("autoOptimizationGeneration")
                ),
            )
        )
    return sorted(candidates, key=lambda item: (item.tier, item.strategy_version_id))

