from __future__ import annotations

from alphapilot.mechanism_breakthrough.contracts import (
    MechanismBreakthroughBudget,
    build_frozen_candidates,
)


def test_budget_inherits_v37i_remaining_capacity_without_reset() -> None:
    budget = MechanismBreakthroughBudget.default(inherited_full_backtests=91)

    assert budget.maximum_campaigns == 2
    assert budget.maximum_candidates == 6
    assert budget.maximum_development_trials == 12
    assert budget.maximum_full_backtests == 6
    assert budget.maximum_formal_candidates == 2
    assert budget.inherited_full_backtests == 91


def test_frozen_a_b_candidates_have_exact_ids_and_advisory_r_exits() -> None:
    candidates = build_frozen_candidates()

    assert [row.candidateId for row in candidates] == [
        "v42_breakout_trap_second_entry_long_4h_v1",
        "v42_breakout_trap_second_entry_short_4h_v1",
        "v42_spike_pullback_continuation_long_1h_v1",
        "v42_spike_pullback_continuation_short_1h_v1",
    ]
    assert all(row.targetR is None for row in candidates)
    assert all(row.exitPolicy is not None for row in candidates)
    assert all(row.to_dict()["targetRGateMode"] == "advisory" for row in candidates)
    assert all(row.to_dict()["initialStopMayWiden"] is False for row in candidates)

