from __future__ import annotations

from pathlib import Path

import pytest

from alphapilot.automatic_candidate_research.contracts import V36ContractError
from alphapilot.automatic_candidate_research.formal_handoff import (
    build_formal_handoff_state,
    resolve_tsmom_formal_handoff,
)
from alphapilot.standard_replication.tsmom_engine import SELECTED_TSMOM_TRIALS


READY_CANDIDATE = "v35_tsmom_crypto_adaptation"
BLOCKED_CANDIDATE = "v35_tsmom_source_replication"


def test_formal_handoff_splits_ready_and_blocked_candidates_without_side_effects() -> None:
    preregistration = _preregistration()
    selections = _selections()

    result = build_formal_handoff_state(
        preregistration=preregistration,
        selections=selections,
        readiness_report=_readiness_report(),
    )

    assert result["status"] == "partially_ready_to_freeze"
    assert result["formalReadyCandidateCount"] == 1
    assert result["blockedCandidateCount"] == 1
    assert result["readyCandidates"] == [
        {
            "candidateId": READY_CANDIDATE,
            "selectedTrialId": SELECTED_TSMOM_TRIALS[READY_CANDIDATE],
            "readinessStatus": "ready",
            "blockers": [],
        }
    ]
    assert result["blockedCandidates"][0]["candidateId"] == BLOCKED_CANDIDATE
    assert result["blockedCandidates"][0]["blockers"] == [
        "purged_walk_forward_capacity_insufficient"
    ]
    assert result["formalRunCount"] == 0
    assert result["formalInputReadCount"] == 0
    assert result["resultReadCount"] == 0
    assert result["releaseCount"] == 0
    assert result["approvalCount"] == 0
    assert result["demoArm"] is False
    assert result["orderCount"] == 0
    assert str(result["handoffHash"]).startswith("v36_formal_handoff_")


def test_formal_handoff_rejects_readiness_trial_identity_drift() -> None:
    readiness = _readiness_report()
    readiness["candidates"][0]["selectedTrialId"] = "trial-drifted"

    with pytest.raises(V36ContractError, match="formal_readiness_trial_mismatch"):
        build_formal_handoff_state(
            preregistration=_preregistration(),
            selections=_selections(),
            readiness_report=readiness,
        )


def test_tsmom_resolver_infers_data_roots_and_preserves_partial_readiness(
    tmp_path: Path,
) -> None:
    snapshot_path = (
        tmp_path
        / "okx_official_v1"
        / "manifests"
        / "snapshot-fixture.json"
    )
    captured: dict[str, object] = {}

    def readiness_builder(**kwargs):
        captured.update(kwargs)
        return _readiness_report()

    result = resolve_tsmom_formal_handoff(
        preregistration=_preregistration(),
        selections=_selections(),
        campaign_input={
            "campaignId": "campaign-formal-handoff",
            "comparisonPanel": {"developmentEnd": "2025-01-01T00:00:00Z"},
            "developmentReplay": {"snapshotManifestPath": str(snapshot_path)},
        },
        readiness_builder=readiness_builder,
    )

    assert result["status"] == "partially_ready_to_freeze"
    assert captured["snapshot_manifest_path"] == snapshot_path.resolve()
    assert captured["funding_root"] == (
        snapshot_path.resolve().parents[2]
        / "_alphapilot"
        / "canonical"
        / "okx"
        / "swap"
        / "funding"
    )
    assert captured["candidate_ids"] == [READY_CANDIDATE, BLOCKED_CANDIDATE]
    assert captured["formal_start"] == "2025-01-01T00:00:00Z"


def _preregistration() -> dict[str, object]:
    return {
        "campaignId": "campaign-formal-handoff",
        "comparisonPanelHash": "comparison-panel-hash",
        "trialsByCandidate": {
            READY_CANDIDATE: [
                {"trialId": SELECTED_TSMOM_TRIALS[READY_CANDIDATE]}
            ],
            BLOCKED_CANDIDATE: [
                {"trialId": SELECTED_TSMOM_TRIALS[BLOCKED_CANDIDATE]}
            ],
        },
    }


def _selections() -> list[dict[str, object]]:
    return [
        {
            "candidateId": READY_CANDIDATE,
            "selectedTrialId": SELECTED_TSMOM_TRIALS[READY_CANDIDATE],
            "eligible": True,
            "lockedOosReadCount": 0,
        },
        {
            "candidateId": BLOCKED_CANDIDATE,
            "selectedTrialId": SELECTED_TSMOM_TRIALS[BLOCKED_CANDIDATE],
            "eligible": True,
            "lockedOosReadCount": 0,
        },
    ]


def _readiness_report() -> dict[str, object]:
    return {
        "schemaVersion": "v36_tsmom_formal_readiness_v1",
        "campaignId": "campaign-formal-handoff",
        "readinessHash": "readiness-fixture-hash",
        "candidates": [
            {
                "candidateId": READY_CANDIDATE,
                "selectedTrialId": SELECTED_TSMOM_TRIALS[READY_CANDIDATE],
                "status": "ready",
                "blockers": [],
            },
            {
                "candidateId": BLOCKED_CANDIDATE,
                "selectedTrialId": SELECTED_TSMOM_TRIALS[BLOCKED_CANDIDATE],
                "status": "blocked",
                "blockers": ["purged_walk_forward_capacity_insufficient"],
            },
        ],
        "formalRunCount": 0,
        "formalInputReadCount": 0,
        "resultReadCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
