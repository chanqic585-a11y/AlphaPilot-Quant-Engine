"""Evidence-bounded failure attribution for archived strategies."""

from __future__ import annotations

from collections import Counter
from typing import Any

from alphapilot.reports.archived_strategy_failure_schema_v2 import FAILURE_LABELS_ZH


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pair_concentration(metrics: dict[str, Any]) -> float | None:
    by_symbol = metrics.get("bySymbol") or {}
    counts = [
        _number(item.get("tradeCount"))
        for item in by_symbol.values()
        if isinstance(item, dict)
    ]
    counts = [item for item in counts if item is not None]
    if not counts or sum(counts) == 0:
        return None
    return max(counts) / sum(counts)


def _split_instability(metrics: dict[str, Any]) -> bool:
    values = []
    for item in (metrics.get("bySplit") or {}).values():
        if isinstance(item, dict):
            pf = _number(item.get("profitFactor"))
            if pf is not None:
                values.append(pf)
    return len(values) >= 2 and min(values) < 1 <= max(values)


def _regime_mismatch(metrics: dict[str, Any]) -> bool:
    values = []
    for key, item in (metrics.get("byRegime") or {}).items():
        if isinstance(item, dict):
            values.append((str(key), _number(item.get("averageNetR"))))
    positives = [key for key, value in values if value is not None and value > 0]
    negatives = [key for key, value in values if value is not None and value <= 0]
    return bool(positives and negatives)


def _exit_failure(metrics: dict[str, Any]) -> bool:
    exits = metrics.get("byExitReason") or {}
    if not exits:
        return False
    total = sum(int(item.get("tradeCount") or 0) for item in exits.values() if isinstance(item, dict))
    stop = sum(
        int(item.get("tradeCount") or 0)
        for key, item in exits.items()
        if "stop" in str(key).lower() and isinstance(item, dict)
    )
    return total > 0 and stop / total >= 0.6


def _confidence(record: dict[str, Any], metrics: dict[str, Any]) -> tuple[str, float]:
    level = int(record.get("evidenceLevel") or 4)
    completeness = _number(record.get("evidenceCompleteness")) or 0.0
    trade_count = _number(metrics.get("tradeCount"))
    score = (5 - level) * 0.18 + completeness * 0.42
    if trade_count is not None and trade_count >= 100:
        score += 0.15
    elif trade_count is not None and trade_count >= 30:
        score += 0.08
    score = round(min(max(score, 0.05), 0.98), 4)
    return ("high" if score >= 0.75 else "medium" if score >= 0.45 else "low"), score


def attribute_archived_failure(record: dict[str, Any]) -> dict[str, Any]:
    metrics = record.get("metrics") or {}
    trade_count = _number(metrics.get("tradeCount"))
    profit_factor = _number(metrics.get("profitFactor"))
    average_net_r = _number(metrics.get("averageNetR"))
    max_drawdown_r = _number(metrics.get("maximumDrawdownR"))
    failure_summary = str(record.get("failureSummary") or "")
    failure_lower = failure_summary.lower()

    if any(term in failure_lower for term in ("martingale", "逆势加仓", "risk design rejected")):
        primary = "rejected_risk_design"
    elif trade_count == 0:
        primary = "zero_trade_or_blocked"
    elif profit_factor is not None and profit_factor < 1:
        primary = "signal_edge_failure"
    elif average_net_r is not None and average_net_r <= 0:
        primary = "signal_edge_failure"
    elif trade_count is not None and trade_count < 30:
        primary = "small_sample"
    elif max_drawdown_r is not None and max_drawdown_r > 10:
        primary = "risk_model_failure"
    elif not metrics or (profit_factor is None and average_net_r is None):
        primary = "data_evidence_gap"
    else:
        primary = "data_evidence_gap"

    secondary: list[str] = []
    stress = metrics.get("costStress") or {}
    stress_net_r = _number(stress.get("averageNetR")) if isinstance(stress, dict) else None
    if stress_net_r is not None and stress_net_r < 0:
        secondary.append("cost_amplification")
    if max_drawdown_r is not None and max_drawdown_r > 5 and primary != "risk_model_failure":
        secondary.append("risk_model_failure")
    if trade_count is not None and trade_count >= 10000 and (average_net_r or 0) <= 0:
        secondary.append("overtrading")
    concentration = _pair_concentration(metrics)
    if concentration is not None and concentration >= 0.5:
        secondary.append("pair_concentration")
    if _split_instability(metrics):
        secondary.append("time_regime_instability")
    if _regime_mismatch(metrics):
        secondary.append("direction_regime_mismatch")
    if _exit_failure(metrics):
        secondary.append("exit_design_failure")
    if int(record.get("evidenceLevel") or 4) >= 3 or (
        _number(record.get("evidenceCompleteness")) or 0
    ) < 0.5:
        secondary.append("data_evidence_gap")
    if record.get("failureCategory") in {"data_integrity", "worker_operational"} or any(
        term in failure_lower for term in ("fault", "blocked", "engineering", "故障", "阻塞")
    ):
        secondary.append("runtime_engineering_failure")
    secondary = sorted(set(item for item in secondary if item != primary))

    confidence, score = _confidence(record, metrics)
    severity = (
        "critical"
        if primary in {"signal_edge_failure", "rejected_risk_design"}
        and (trade_count or 0) >= 100
        else "high"
        if primary in {"signal_edge_failure", "risk_model_failure", "zero_trade_or_blocked"}
        else "medium"
    )
    return {
        "strategyId": record.get("strategyId"),
        "strategyName": record.get("strategyName"),
        "strategyFamily": record.get("strategyFamily"),
        "timeframe": record.get("timeframe"),
        "status": record.get("status"),
        "primaryFailureType": primary,
        "primaryFailureLabelZh": FAILURE_LABELS_ZH[primary],
        "secondaryFailureTypes": secondary,
        "secondaryFailureLabelsZh": [FAILURE_LABELS_ZH[item] for item in secondary],
        "severity": severity,
        "confidence": confidence,
        "confidenceScore": score,
        "causalityProven": False,
        "signalLayer": {
            "assessment": (
                "failed"
                if primary == "signal_edge_failure"
                else "insufficient" if profit_factor is None and average_net_r is None else "not_primary_failure"
            ),
            "profitFactor": profit_factor,
            "averageNetR": average_net_r,
        },
        "accountRiskLayer": {
            "assessment": (
                "failed"
                if primary == "risk_model_failure" or "risk_model_failure" in secondary
                else "insufficient" if max_drawdown_r is None else "not_primary_failure"
            ),
            "maximumDrawdownR": max_drawdown_r,
        },
        "costLayer": {
            "assessment": "failed" if "cost_amplification" in secondary else "insufficient_or_not_primary",
            "costStressAverageNetR": stress_net_r,
        },
        "evidenceBasis": {
            "evidenceLevel": record.get("evidenceLevel"),
            "evidenceCompleteness": record.get("evidenceCompleteness"),
            "tradeCount": trade_count,
            "failureSummary": failure_summary or None,
        },
        "limitations": [
            "归因是证据相关性判断，不证明单一因果关系。",
            "缺失值没有被替换为 0 或通过证据。",
        ],
    }


def build_cross_strategy_patterns(attributions: list[dict[str, Any]]) -> dict[str, Any]:
    primary = Counter(item.get("primaryFailureType") for item in attributions)
    secondary = Counter(
        failure
        for item in attributions
        for failure in item.get("secondaryFailureTypes") or []
    )
    by_timeframe: dict[str, Counter[str]] = {}
    by_family: dict[str, Counter[str]] = {}
    for item in attributions:
        timeframe = str(item.get("timeframe") or "unknown")
        by_timeframe.setdefault(timeframe, Counter())[str(item.get("primaryFailureType"))] += 1
        family = str(item.get("strategyFamily") or item.get("strategyId") or "unknown")
        by_family.setdefault(family, Counter())[str(item.get("primaryFailureType"))] += 1
    dominant_family_failures = Counter(
        counts.most_common(1)[0][0] for counts in by_family.values() if counts
    )
    return {
        "primaryFailureCounts": dict(sorted(primary.items())),
        "secondaryFailureCounts": dict(sorted(secondary.items())),
        "uniqueFamilyCount": len(by_family),
        "dominantPrimaryFailureByFamilyCounts": dict(sorted(dominant_family_failures.items())),
        "primaryFailureByTimeframe": {
            timeframe: dict(sorted(counts.items()))
            for timeframe, counts in sorted(by_timeframe.items())
        },
        "interpretation": [
            "共性模式只用于提出下一轮可证伪假设，不能自动生成可执行资格。",
            "自动优化版本必须按家族和父子链去重后再解读，避免把同源失败误当独立证据。",
        ],
    }
