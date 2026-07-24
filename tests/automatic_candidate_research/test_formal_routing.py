from __future__ import annotations

import pytest

from alphapilot.automatic_candidate_research.contracts import V36ContractError
from alphapilot.automatic_candidate_research.formal_routing import route_formal_outcomes


def test_only_formal_pass_emits_safe_immutable_release() -> None:
    result = route_formal_outcomes(
        preregistration=_preregistration(),
        selections=[
            _selection("candidate-a", "trial-a"),
            _selection("candidate-b", "trial-b"),
        ],
        formal_outcomes=[
            _formal("candidate-a", "trial-a", "formal_pass", locked_reads=1),
            _formal(
                "candidate-b",
                "trial-b",
                "research_pass_no_clean_holdout",
                locked_reads=0,
            ),
        ],
    )

    assert result["formalRunCount"] == 2
    assert result["resultReadCount"] == 2
    assert result["lockedOosReadCount"] == 1
    assert result["releaseCount"] == 1
    release = result["immutableReleases"][0]
    assert release["candidateId"] == "candidate-a"
    assert release["trialId"] == "trial-a"
    assert release["outcome"] == "formal_pass"
    assert release["approved"] is False
    assert release["demoArm"] is False
    assert release["orders"] == 0
    assert release["immutableReleaseHash"].startswith("v36_immutable_release_")


def test_zero_winner_and_data_blocked_are_valid_results() -> None:
    result = route_formal_outcomes(
        preregistration=_preregistration(),
        selections=[],
        formal_outcomes=[],
    )

    assert result["status"] == "research_blocked_data"
    assert result["blockedFamilyIds"] == ["blocked-family"]
    assert result["formalRunCount"] == 0
    assert result["resultReadCount"] == 0
    assert result["lockedOosReadCount"] == 0
    assert result["releaseCount"] == 0
    assert result["immutableReleases"] == []


def test_stable_selection_without_formal_evidence_waits_for_formal_validation() -> None:
    preregistration = _preregistration()
    preregistration["blockedFamilyIds"] = []

    result = route_formal_outcomes(
        preregistration=preregistration,
        selections=[_selection("candidate-a", "trial-a")],
        formal_outcomes=[],
    )

    assert result["status"] == "awaiting_formal_validation"
    assert result["formalRunCount"] == 0
    assert result["resultReadCount"] == 0
    assert result["releaseCount"] == 0


def test_no_stable_selection_is_zero_qualified_when_data_is_available() -> None:
    preregistration = _preregistration()
    preregistration["blockedFamilyIds"] = []

    result = route_formal_outcomes(
        preregistration=preregistration,
        selections=[],
        formal_outcomes=[],
    )

    assert result["status"] == "research_zero_qualified"
    assert result["formalRunCount"] == 0
    assert result["releaseCount"] == 0


def test_formal_route_rejects_panel_drift_and_unknown_outcome() -> None:
    drifted = _formal("candidate-a", "trial-a", "formal_pass", locked_reads=1)
    drifted["comparisonPanelHash"] = "wrong-panel"
    with pytest.raises(V36ContractError, match="comparison_panel_identity_mismatch"):
        route_formal_outcomes(
            preregistration=_preregistration(),
            selections=[_selection("candidate-a", "trial-a")],
            formal_outcomes=[drifted],
        )


def test_formal_route_rejects_trial_not_in_preregistration() -> None:
    with pytest.raises(V36ContractError, match="formal_trial_not_preregistered"):
        route_formal_outcomes(
            preregistration=_preregistration(),
            selections=[_selection("candidate-a", "trial-never-frozen")],
            formal_outcomes=[],
        )

    with pytest.raises(V36ContractError, match="unsupported_formal_outcome"):
        route_formal_outcomes(
            preregistration=_preregistration(),
            selections=[_selection("candidate-a", "trial-a")],
            formal_outcomes=[_formal("candidate-a", "trial-a", "made_up", locked_reads=1)],
        )


def test_formal_route_rejects_duplicate_candidate_trial_evidence() -> None:
    duplicate = _formal("candidate-a", "trial-a", "formal_pass", locked_reads=1)

    with pytest.raises(V36ContractError, match="duplicate_formal_outcome"):
        route_formal_outcomes(
            preregistration=_preregistration(),
            selections=[_selection("candidate-a", "trial-a")],
            formal_outcomes=[duplicate, dict(duplicate)],
        )


def _preregistration() -> dict[str, object]:
    return {
        "campaignId": "v36-campaign",
        "preregistrationHash": "v36_preregistration_abc",
        "comparisonPanelHash": "v36_comparison_panel_abc",
        "blockedFamilyIds": ["blocked-family"],
        "trialsByCandidate": {
            "candidate-a": [{"trialId": "trial-a"}],
            "candidate-b": [{"trialId": "trial-b"}],
        },
    }


def _selection(candidate_id: str, trial_id: str) -> dict[str, object]:
    return {
        "candidateId": candidate_id,
        "selectedTrialId": trial_id,
        "eligible": True,
        "lockedOosReadCount": 0,
    }


def _formal(
    candidate_id: str,
    trial_id: str,
    outcome: str,
    *,
    locked_reads: int,
) -> dict[str, object]:
    return {
        "candidateId": candidate_id,
        "trialId": trial_id,
        "comparisonPanelHash": "v36_comparison_panel_abc",
        "formalArtifactHash": f"formal-artifact-{candidate_id}",
        "outcome": outcome,
        "lockedOosReadCount": locked_reads,
    }
