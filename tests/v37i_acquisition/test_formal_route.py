from __future__ import annotations

from alphapilot.v37i_acquisition.formal_route import build_v37j_route


def test_zero_survivors_is_a_valid_terminal_state() -> None:
    route = build_v37j_route(
        candidate_rows=[
            {"candidateId": "candidate-a", "prefilterPassed": False},
            {"candidateId": "candidate-b", "prefilterPassed": False},
        ]
    )

    assert route["status"] == "completed_zero_qualified_candidates"
    assert route["formalCandidateCount"] == 0
    assert route["formalRunCount"] == 0
    assert route["resultReadCount"] == 0
    assert route["lockedOosReadCount"] == 0
    assert route["releaseCount"] == 0
    assert route["demoArm"] is False
    assert route["orders"] == 0


def test_only_prefilter_survivors_can_enter_formal_freeze_queue() -> None:
    route = build_v37j_route(
        candidate_rows=[
            {"candidateId": "candidate-a", "prefilterPassed": True},
            {"candidateId": "candidate-b", "prefilterPassed": False},
        ]
    )

    assert route["status"] == "formal_freeze_required"
    assert route["formalCandidateIds"] == ["candidate-a"]
    assert route["formalRunCount"] == 0
    assert route["releaseCount"] == 0
