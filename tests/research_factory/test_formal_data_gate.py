from __future__ import annotations

from alphapilot.research_factory.formal_data_gate import evaluate_formal_data_gate


def test_formal_claim_is_blocked_without_consuming_budget() -> None:
    decision = evaluate_formal_data_gate(
        all_formal_required_fields_semantically_verified=False,
        formal_data_profile_status="blocked",
        formal_event_capacity_input_coverage=0.0,
        minimum_capacity_input_coverage=0.95,
    )

    assert decision["status"] == "formal_data_blocked_before_claim"
    assert decision["claimPermitted"] is False
    assert decision["formalRunBudgetConsumed"] == 0
    assert decision["ledgerDelta"] == {
        "claimCount": 0,
        "attemptCount": 0,
        "resultCount": 0,
        "resultReadCount": 0,
    }


def test_formal_claim_is_ready_only_when_all_hard_conditions_pass() -> None:
    decision = evaluate_formal_data_gate(
        all_formal_required_fields_semantically_verified=True,
        formal_data_profile_status="ready",
        formal_event_capacity_input_coverage=0.97,
        minimum_capacity_input_coverage=0.95,
    )

    assert decision["status"] == "ready_for_formal_claim"
    assert decision["claimPermitted"] is True
    assert decision["failedConditions"] == []
