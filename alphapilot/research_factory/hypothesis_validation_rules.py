"""Point-in-time condition rules for V13.4.26 hypothesis validation."""

from __future__ import annotations

from typing import Any

import pandas as pd

from alphapilot.research_factory.hypothesis_validation_schema import HypothesisValidationRule

HIGH_PRIORITY_HYPOTHESIS_IDS = ["HYP-001", "HYP-002", "HYP-004", "HYP-006", "HYP-007", "HYP-008"]


def build_hypothesis_validation_rules(hypotheses: list[dict[str, Any]]) -> list[HypothesisValidationRule]:
    hypothesis_by_id = {str(item.get("hypothesisId")): item for item in hypotheses}
    rules: list[HypothesisValidationRule] = []
    for hypothesis_id in HIGH_PRIORITY_HYPOTHESIS_IDS:
        if hypothesis_id not in hypothesis_by_id:
            continue
        rules.append(_rule_for_hypothesis(hypothesis_id))
    return rules


def _rule_for_hypothesis(hypothesis_id: str) -> HypothesisValidationRule:
    mapping = {
        "HYP-001": HypothesisValidationRule(
            hypothesisId="HYP-001",
            conditionId="acceptable_volatility_atr_context",
            description="Pass when current volatility_3d and atr_pct are not in the highest cross-sectional risk quartile.",
            requiredColumns=["volatility_3d", "atr_pct", "volatilityRankPct", "atrRankPct"],
            noLookaheadNotes=["Uses current timestamp cross-sectional ranks only."],
        ),
        "HYP-002": HypothesisValidationRule(
            hypothesisId="HYP-002",
            conditionId="top_trend_strength_regime",
            description="Pass when trend_strength is in the top cross-sectional third at the current timestamp.",
            requiredColumns=["trend_strength", "trendStrengthRankPct"],
            noLookaheadNotes=["Uses current timestamp cross-sectional trend rank only."],
        ),
        "HYP-004": HypothesisValidationRule(
            hypothesisId="HYP-004",
            conditionId="bollinger_lower_non_crash_regime",
            description="Pass when bollinger_position is near the lower band, regime is not trend_down, and BTC 12h momentum is not crash-like.",
            requiredColumns=["bollinger_position", "regimeLabel", "btc_momentum_12"],
            noLookaheadNotes=["Uses current Bollinger position, current regime label, and current BTC momentum only."],
        ),
        "HYP-006": HypothesisValidationRule(
            hypothesisId="HYP-006",
            conditionId="low_frequency_quality_context",
            description="Pass when strict rebound, acceptable volatility, and medium/high liquidity context all agree.",
            requiredColumns=["bollinger_position", "volatilityRankPct", "atrRankPct", "liquidity_rank", "regimeLabel"],
            noLookaheadNotes=["Uses only current factor values and current cross-sectional ranks."],
        ),
        "HYP-007": HypothesisValidationRule(
            hypothesisId="HYP-007",
            conditionId="liquidity_gate_first",
            description="Pass when liquidity_rank is at least the top third or liquidityBucket is high.",
            requiredColumns=["liquidity_rank", "liquidityBucket"],
            noLookaheadNotes=["Uses current timestamp liquidity rank and current pair liquidity bucket only."],
        ),
        "HYP-008": HypothesisValidationRule(
            hypothesisId="HYP-008",
            conditionId="benchmarkable_universe_with_btc_context",
            description="Pass when the row is in the local research universe and BTC forward comparison labels are available.",
            requiredColumns=["universeMember", "btcForwardReturn_12"],
            noLookaheadNotes=["Condition uses universe membership only; BTC forward return is used for evaluation metrics, not condition construction."],
        ),
    }
    return mapping[hypothesis_id]


def apply_validation_rule(panel: pd.DataFrame, rule: HypothesisValidationRule) -> tuple[pd.Series, pd.Series, list[str]]:
    missing = [column for column in rule.requiredColumns if column not in panel.columns]
    if missing:
        false_mask = pd.Series(False, index=panel.index)
        reason = pd.Series(f"missing_columns:{','.join(missing)}", index=panel.index)
        return false_mask, reason, [f"{rule.hypothesisId} validation skipped missing columns: {', '.join(missing)}"]

    if rule.hypothesisId == "HYP-001":
        mask = (pd.to_numeric(panel["volatilityRankPct"], errors="coerce") <= 0.75) & (
            pd.to_numeric(panel["atrRankPct"], errors="coerce") <= 0.75
        )
        reason = _reason(mask, "volatility_and_atr_not_extreme", "volatility_or_atr_extreme_or_missing", panel.index)
        return mask.fillna(False), reason, []

    if rule.hypothesisId == "HYP-002":
        mask = pd.to_numeric(panel["trendStrengthRankPct"], errors="coerce") >= 0.67
        reason = _reason(mask, "trend_strength_top_third", "trend_strength_not_top_third_or_missing", panel.index)
        return mask.fillna(False), reason, []

    if rule.hypothesisId == "HYP-004":
        bollinger = pd.to_numeric(panel["bollinger_position"], errors="coerce")
        btc_momentum = pd.to_numeric(panel["btc_momentum_12"], errors="coerce")
        regime = panel["regimeLabel"].astype(str)
        mask = (bollinger <= 0.25) & (regime != "trend_down") & (btc_momentum > -0.02)
        reason = _reason(mask, "lower_band_rebound_non_crash", "not_lower_band_or_crash_regime_or_missing", panel.index)
        return mask.fillna(False), reason, []

    if rule.hypothesisId == "HYP-006":
        bollinger = pd.to_numeric(panel["bollinger_position"], errors="coerce")
        volatility = pd.to_numeric(panel["volatilityRankPct"], errors="coerce")
        atr = pd.to_numeric(panel["atrRankPct"], errors="coerce")
        liquidity = pd.to_numeric(panel["liquidity_rank"], errors="coerce")
        regime = panel["regimeLabel"].astype(str)
        mask = (bollinger <= 0.2) & (volatility <= 0.6) & (atr <= 0.6) & (liquidity >= 50) & (regime != "trend_down")
        reason = _reason(mask, "strict_low_frequency_quality_context", "strict_quality_context_not_met_or_missing", panel.index)
        return mask.fillna(False), reason, []

    if rule.hypothesisId == "HYP-007":
        liquidity = pd.to_numeric(panel["liquidity_rank"], errors="coerce")
        bucket = panel["liquidityBucket"].astype(str)
        mask = (liquidity >= 67) | (bucket == "high")
        reason = _reason(mask, "liquidity_gate_passed", "liquidity_gate_failed_or_missing", panel.index)
        return mask.fillna(False), reason, []

    if rule.hypothesisId == "HYP-008":
        universe_member = panel["universeMember"].fillna(False).astype(bool)
        btc_forward = pd.to_numeric(panel["btcForwardReturn_12"], errors="coerce")
        mask = universe_member & btc_forward.notna()
        reason = _reason(mask, "benchmarkable_with_btc_forward_context", "not_benchmarkable_or_missing_btc_context", panel.index)
        return mask.fillna(False), reason, []

    false_mask = pd.Series(False, index=panel.index)
    return false_mask, pd.Series("unknown_rule", index=panel.index), [f"No validation rule found for {rule.hypothesisId}."]


def _reason(mask: pd.Series, pass_reason: str, fail_reason: str, index: pd.Index) -> pd.Series:
    reason = pd.Series(fail_reason, index=index)
    reason.loc[mask.fillna(False)] = pass_reason
    return reason
