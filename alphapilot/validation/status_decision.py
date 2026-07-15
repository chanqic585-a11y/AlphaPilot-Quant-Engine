"""Locked candidate status decisions with non-rescuable primary risk gates."""

from __future__ import annotations

from typing import Any, Mapping


_STATUS_DISPLAY_ZH = {
    "signal_unreproducible": "信号不可复现",
    "prefilter_stopped": "预筛选停止",
    "locked_sample_unavailable": "锁定样本不可用",
    "sample_insufficient": "有效样本不足",
    "failed_signal": "信号层未通过",
    "failed_locked": "锁定样本层未通过",
    "failed_cost": "成本压力层未通过",
    "failed_stability": "稳定性层未通过",
    "failed_risk": "账户风险层未通过",
    "passed": "锁定验证通过",
}

_DECISION_ORDER = (
    ("signalReproducible", False, "signal_unreproducible"),
    ("prefilterPassed", False, "prefilter_stopped"),
    ("cleanLockedSampleAvailable", False, "locked_sample_unavailable"),
    ("sampleSufficient", False, "sample_insufficient"),
    ("signalPassed", False, "failed_signal"),
    ("lockedPassed", False, "failed_locked"),
    ("costPassed", False, "failed_cost"),
    ("stabilityPassed", False, "failed_stability"),
    ("primaryRiskPassed", False, "failed_risk"),
)


def decide_candidate_status(
    gates: Mapping[str, bool],
    *,
    sensitivity_results: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve one final status from preregistered gates in fixed order.

    Risk models 2 and 3 are sensitivity-only. Their results are retained for
    diagnostics but can never rescue a failure in primary risk model 1.
    """

    status = "passed"
    for gate_name, expected_failure_value, failure_status in _DECISION_ORDER:
        if gates.get(gate_name) is expected_failure_value:
            status = failure_status
            break

    return {
        "status": status,
        "displayStatusZh": _STATUS_DISPLAY_ZH[status],
        "hardPass": status == "passed",
        "sensitivityCanRescuePrimaryFailure": False,
        "sensitivityResults": dict(sensitivity_results),
    }
