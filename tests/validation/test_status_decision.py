from __future__ import annotations

from alphapilot.validation.status_decision import decide_candidate_status


def _gates() -> dict:
    return {
        "signalReproducible": True,
        "prefilterPassed": True,
        "cleanLockedSampleAvailable": True,
        "sampleSufficient": True,
        "signalPassed": True,
        "lockedPassed": True,
        "costPassed": True,
        "stabilityPassed": True,
        "primaryRiskPassed": True,
    }


def test_primary_risk_failure_cannot_be_rescued_by_sensitivity_models() -> None:
    gates = _gates()
    gates["primaryRiskPassed"] = False

    result = decide_candidate_status(
        gates,
        sensitivity_results={"model_2": True, "model_3": True},
    )

    assert result["status"] == "failed_risk"
    assert result["displayStatusZh"] == "账户风险层未通过"
    assert result["sensitivityCanRescuePrimaryFailure"] is False


def test_contaminated_locked_sample_blocks_otherwise_positive_candidate() -> None:
    gates = _gates()
    gates["cleanLockedSampleAvailable"] = False

    result = decide_candidate_status(gates, sensitivity_results={})

    assert result["status"] == "locked_sample_unavailable"
    assert result["hardPass"] is False


def test_prefilter_stops_thin_edge_candidate_before_full_validation() -> None:
    gates = _gates()
    gates["prefilterPassed"] = False

    result = decide_candidate_status(gates, sensitivity_results={})

    assert result["status"] == "prefilter_stopped"


def test_all_primary_gates_are_required_for_pass() -> None:
    result = decide_candidate_status(_gates(), sensitivity_results={})

    assert result["status"] == "passed"
    assert result["hardPass"] is True


def test_locked_and_stability_failures_have_distinct_statuses() -> None:
    locked = _gates()
    locked["lockedPassed"] = False
    stability = _gates()
    stability["stabilityPassed"] = False

    assert decide_candidate_status(locked, sensitivity_results={})["status"] == "failed_locked"
    assert decide_candidate_status(stability, sensitivity_results={})["status"] == "failed_stability"
