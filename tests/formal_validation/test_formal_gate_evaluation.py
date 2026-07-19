from __future__ import annotations

from alphapilot.formal_validation.formal_gate_evaluation import (
    build_fold_assignment_gate,
    evaluate_formal_gates,
)


def _gate(
    gate_id: str,
    *,
    passed: bool | None,
    gate_class: str = "admission",
    route_class: str | None = None,
) -> dict:
    return {
        "gateId": gate_id,
        "actual": 0,
        "threshold": 0,
        "status": "unavailable" if passed is None else ("passed" if passed else "failed"),
        "passed": passed,
        "gateClass": gate_class,
        "routeClass": route_class,
        "reasonCode": None if passed is True else f"{gate_id}_not_passed",
        "evidenceRefs": [f"evidence/{gate_id}.json"],
    }


def test_legal_fold_exclusions_do_not_fail_assignment_gate() -> None:
    row = build_fold_assignment_gate(
        {
            "explicitlyExcludedEventCount": 37,
            "excludedEventCount": 37,
            "unclassifiedEventCount": 0,
            "multiAssignedEventCount": 0,
            "unknownDispositionCount": 0,
            "crossBoundaryLeakageCount": 0,
        }
    )

    assert row["passed"] is True
    assert row["actual"] == 0
    assert row["legalExcludedEventCount"] == 37


def test_only_forbidden_fold_outcomes_fail_assignment_gate() -> None:
    row = build_fold_assignment_gate(
        {
            "explicitlyExcludedEventCount": 9,
            "unclassifiedEventCount": 1,
            "multiAssignedEventCount": 2,
            "unknownDispositionCount": 3,
            "crossBoundaryLeakageCount": 4,
        }
    )

    assert row["passed"] is False
    assert row["actual"] == 10
    assert row["violations"] == {
        "unclassifiedEventCount": 1,
        "multiAssignedEventCount": 2,
        "unknownDispositionCount": 3,
        "crossBoundaryLeakageCount": 4,
    }


def test_one_evaluation_drives_route_failure_and_summary_blockers() -> None:
    evaluation = evaluate_formal_gates(
        gate_rows=[
            _gate("translation_parity", passed=True),
            _gate("minimum_profit_factor", passed=False),
            _gate(
                "diagnostic_sample_shape",
                passed=False,
                gate_class="diagnostic",
            ),
        ],
        implementation_blockers=[],
        stopping_rules={
            "economicGateFailure": "archive_candidate",
            "implementationInvalid": "implementation_invalid",
        },
        comparable_candidate_panel_status="available",
    )

    assert evaluation.route == "archive_candidate"
    assert evaluation.blockers == ("minimum_profit_factor",)
    assert evaluation.gate_matrix["failedAdmissionGateIds"] == [
        "minimum_profit_factor"
    ]
    assert evaluation.route_payload("campaign-1")["blockers"] == [
        "minimum_profit_factor"
    ]
    assert evaluation.failure_attribution("campaign-1")["blockers"] == [
        "minimum_profit_factor"
    ]
    assert evaluation.summary_fields()["blockers"] == ["minimum_profit_factor"]
    assert evaluation.gate_matrix["failedDiagnosticGateIds"] == [
        "diagnostic_sample_shape"
    ]


def test_every_failed_implementation_admission_gate_is_routed() -> None:
    evaluation = evaluate_formal_gates(
        gate_rows=[
            _gate("translation_parity", passed=False),
            _gate("fold_assignment_complete", passed=False),
        ],
        implementation_blockers=["canonical_event_identity_mapping_incomplete"],
        stopping_rules={"implementationInvalid": "implementation_invalid"},
        comparable_candidate_panel_status="available",
    )

    assert evaluation.route == "implementation_invalid"
    assert evaluation.blockers == (
        "canonical_event_identity_mapping_incomplete",
        "translation_parity",
        "fold_assignment_complete",
    )


def test_gate_schema_uses_class_for_admission_and_route_class_for_failure_type() -> None:
    evaluation = evaluate_formal_gates(
        gate_rows=[
            _gate(
                "translation_parity",
                passed=False,
                gate_class="admission",
                route_class="implementation",
            ),
            _gate(
                "diagnostic_sample_shape",
                passed=False,
                gate_class="diagnostic",
                route_class="economic",
            ),
        ],
        implementation_blockers=[],
        stopping_rules={"implementationInvalid": "implementation_invalid"},
        comparable_candidate_panel_status="available",
    )

    rows = evaluation.gate_matrix["gates"]
    assert rows[0]["gateClass"] == "admission"
    assert rows[0]["routeClass"] == "implementation"
    assert rows[0]["reasonCode"] == "translation_parity_not_passed"
    assert rows[0]["evidenceRefs"] == ["evidence/translation_parity.json"]
    assert rows[1]["gateClass"] == "diagnostic"
    assert evaluation.route == "implementation_invalid"


def test_funding_not_evaluable_can_be_a_route_cap_instead_of_gate_failure() -> None:
    evaluation = evaluate_formal_gates(
        gate_rows=[_gate("conservative_funding_average_net_r", passed=None)],
        implementation_blockers=[],
        stopping_rules={},
        comparable_candidate_panel_status="available",
        funding_unavailable_is_route_cap=True,
    )

    assert evaluation.route == "walk_forward_research_pass_no_clean_holdout"
    assert evaluation.blockers == ("clean_locked_oos_unavailable",)
    assert evaluation.gate_matrix["notEvaluableAdmissionGateIds"] == [
        "conservative_funding_average_net_r"
    ]
