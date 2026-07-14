"""Failure attribution helpers for archived strategy research.

The rules are descriptive, not causal.  They classify observed evidence and
keep signal-edge findings separate from account/risk-model findings.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_negative(value: Any) -> bool:
    number = _number(value)
    return number is not None and number < 0


def _is_below(value: Any, threshold: float) -> bool:
    number = _number(value)
    return number is not None and number < threshold


def _is_at_least(value: Any, threshold: float) -> bool:
    number = _number(value)
    return number is not None and number >= threshold


def _signal_layer(metrics: dict[str, Any]) -> dict[str, Any]:
    failed_checks: list[str] = []
    observed_checks: list[str] = []
    profit_factor = _number(metrics.get("profitFactor"))
    total_return = _number(metrics.get("totalReturnPct"))
    average_net_r = _number(metrics.get("averageNetR"))
    if profit_factor is not None:
        observed_checks.append("profitFactor")
        if profit_factor < 1:
            failed_checks.append("profitFactorBelowOne")
    if total_return is not None:
        observed_checks.append("totalReturnPct")
        if total_return < 0:
            failed_checks.append("negativeTotalReturn")
    if average_net_r is not None:
        observed_checks.append("averageNetR")
        if average_net_r <= 0:
            failed_checks.append("nonPositiveAverageNetR")
    if failed_checks:
        assessment = "failed"
    elif observed_checks:
        assessment = "not_failed_on_available_metrics"
    else:
        assessment = "inconclusive_missing_evidence"
    return {
        "assessment": assessment,
        "failedChecks": failed_checks,
        "observedChecks": observed_checks,
        "interpretation": (
            "Available trade-level aggregates do not support a positive signal edge."
            if failed_checks
            else "Signal-edge evidence is incomplete or not negative on available metrics."
        ),
    }


def _account_risk_layer(metrics: dict[str, Any]) -> dict[str, Any]:
    failed_checks: list[str] = []
    observed_checks: list[str] = []
    drawdown = _number(metrics.get("maxDrawdownPct"))
    consecutive_losses = _number(metrics.get("maxConsecutiveLosses"))
    if drawdown is not None:
        observed_checks.append("maxDrawdownPct")
        if drawdown >= 30:
            failed_checks.append("maxDrawdownAtLeastThirtyPct")
    if consecutive_losses is not None:
        observed_checks.append("maxConsecutiveLosses")
        if consecutive_losses >= 15:
            failed_checks.append("longConsecutiveLossSequence")
    if failed_checks:
        assessment = "failed"
    elif observed_checks:
        assessment = "not_failed_on_available_metrics"
    else:
        assessment = "inconclusive_missing_evidence"
    return {
        "assessment": assessment,
        "failedChecks": failed_checks,
        "observedChecks": observed_checks,
        "interpretation": (
            "Observed account-path risk is unacceptable for promotion."
            if failed_checks
            else "Account-path evidence is incomplete or below the descriptive failure thresholds."
        ),
    }


def attribute_strategy_failure(record: dict[str, Any]) -> dict[str, Any]:
    metrics = record.get("metrics") or {}
    reason = str(record.get("reason") or "").lower()
    strategy_id = str(record.get("strategyId") or "")
    secondary: list[str] = []

    if "martingale" in strategy_id.lower() or "martingale" in reason or "tail risk" in reason:
        primary = "rejected_risk_design"
    elif (
        metrics.get("tradeCount") is None
        and metrics.get("profitFactor") is None
        and metrics.get("totalReturnPct") is None
    ):
        primary = "data_evidence_gap"
    elif _is_below(metrics.get("profitFactor"), 1) or _is_negative(metrics.get("totalReturnPct")):
        primary = "signal_edge_failure"
    elif "runtime" in reason or "engineering" in reason:
        primary = "runtime_engineering_failure"
    else:
        primary = "data_evidence_gap"

    raw_return = _number(metrics.get("totalReturnPct"))
    adjusted_return = _number(metrics.get("slippageAdjustedTotalReturnPct"))
    raw_pf = _number(metrics.get("profitFactor"))
    adjusted_pf = _number(metrics.get("slippageAdjustedProfitFactor"))
    if (
        raw_return is not None
        and adjusted_return is not None
        and adjusted_return < raw_return
    ) or (raw_pf is not None and adjusted_pf is not None and adjusted_pf < raw_pf):
        secondary.append("cost_amplification")
    if _is_at_least(metrics.get("maxDrawdownPct"), 30) or _is_at_least(
        metrics.get("maxConsecutiveLosses"), 15
    ):
        secondary.append("risk_model_failure")
    if _is_at_least(metrics.get("tradeCount"), 1000) or "excessive trade" in reason or "frequency" in reason:
        secondary.append("overtrading")
    if "pair" in reason or "concentration" in reason:
        secondary.append("pair_concentration")
    if "exit" in reason or "stop" in reason:
        secondary.append("exit_design_failure")
    if record.get("direction") == "short" and "perTradeRegimeAttribution" in (
        record.get("missingEvidenceFields") or []
    ):
        secondary.extend(["direction_regime_mismatch", "data_evidence_gap"])
    if record.get("missingEvidenceFields") and primary != "data_evidence_gap":
        secondary.append("data_evidence_gap")
    secondary = list(dict.fromkeys(item for item in secondary if item != primary))

    severe_signal = (
        _is_below(metrics.get("profitFactor"), 0.7)
        or _is_below(metrics.get("totalReturnPct"), -50)
    )
    severe_risk = _is_at_least(metrics.get("maxDrawdownPct"), 80)
    if primary == "rejected_risk_design" or severe_risk or severe_signal:
        severity = "critical"
    elif primary == "signal_edge_failure" or secondary:
        severity = "high"
    else:
        severity = "medium"

    signal_layer = _signal_layer(metrics)
    account_risk_layer = _account_risk_layer(metrics)
    observations = [
        f"primary={primary}",
        f"signalLayer={signal_layer['assessment']}",
        f"accountRiskLayer={account_risk_layer['assessment']}",
    ]
    if adjusted_return is not None and raw_return is not None:
        observations.append(
            f"slippageReturnDeltaPct={round(adjusted_return - raw_return, 6)}"
        )

    return {
        "strategyId": record.get("strategyId"),
        "strategyName": record.get("strategyName"),
        "strategyFamily": record.get("strategyFamily"),
        "timeframe": record.get("timeframe"),
        "direction": record.get("direction"),
        "primaryFailureType": primary,
        "secondaryFailureTypes": secondary,
        "severity": severity,
        "signalLayer": signal_layer,
        "accountRiskLayer": account_risk_layer,
        "observations": observations,
        "evidenceLevel": record.get("evidenceLevel"),
        "missingEvidenceFields": record.get("missingEvidenceFields") or [],
        "causalityProven": False,
        "attributionLimit": (
            "Classification describes observed associations in existing evidence; "
            "it does not prove a single causal mechanism."
        ),
    }


def build_cross_strategy_patterns(attributions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primary = Counter(row.get("primaryFailureType") for row in attributions)
    secondary = Counter(
        failure
        for row in attributions
        for failure in row.get("secondaryFailureTypes") or []
    )
    patterns: list[dict[str, Any]] = []
    for failure_type, count in primary.most_common():
        patterns.append(
            {
                "patternId": f"primary_{failure_type}",
                "failureType": failure_type,
                "role": "primary",
                "strategyCount": count,
                "interpretation": "Observed repeatedly across archived strategy records.",
                "causalityProven": False,
            }
        )
    for failure_type, count in secondary.most_common():
        if count < 2:
            continue
        patterns.append(
            {
                "patternId": f"secondary_{failure_type}",
                "failureType": failure_type,
                "role": "secondary",
                "strategyCount": count,
                "interpretation": "Recurring secondary weakness in available evidence.",
                "causalityProven": False,
            }
        )
    return patterns
