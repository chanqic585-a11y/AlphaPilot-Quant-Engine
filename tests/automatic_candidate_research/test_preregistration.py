from __future__ import annotations

from pathlib import Path

from alphapilot.automatic_candidate_research.preregistration import (
    build_preregistration,
)
from alphapilot.standard_replication import ReplicationSourceRegistry


def _registry() -> ReplicationSourceRegistry:
    root = Path(__file__).resolve().parents[2]
    return ReplicationSourceRegistry.load(
        root
        / "research"
        / "source_registry"
        / "strategy_research_source_registry.json"
    )


def _panel() -> dict[str, object]:
    return {
        "developmentStart": "2020-01-01T00:00:00Z",
        "developmentEnd": "2025-12-31T23:59:59Z",
        "dataSnapshotId": "okx-public-snapshot-v34c",
        "costPolicyHash": "cost-policy-v1",
        "capitalPolicyHash": "capital-policy-v1",
        "benchmarkPolicyHash": "benchmark-policy-v1",
        "randomSeed": 3601,
    }


def test_preregistration_freezes_three_trials_per_eligible_candidate() -> None:
    first = build_preregistration(
        registry=_registry(),
        campaign_id="v36-bounded-smoke",
        created_at="2026-07-19T00:00:00Z",
        comparison_panel=_panel(),
    )
    second = build_preregistration(
        registry=_registry(),
        campaign_id="v36-bounded-smoke",
        created_at="2026-07-19T00:00:00Z",
        comparison_panel=_panel(),
    )

    assert first == second
    assert first["candidateCount"] == 9
    assert first["eligibleCandidateCount"] == 6
    assert first["trialCount"] == 18
    assert len(first["trialsByCandidate"]) == 6
    assert all(len(trials) == 3 for trials in first["trialsByCandidate"].values())
    assert first["blockedFamilyIds"] == [
        "crypto_cross_sectional_factor_v1",
        "crypto_event_driven_v1",
    ]
    assert first["contextOnlyCandidateIds"] == ["v35_chan_context_replication"]
    assert first["lockedOosReadCount"] == 0
    assert first["comparisonPanel"]["dataSnapshotId"] == "okx-public-snapshot-v34c"
    assert first["comparisonPanelHash"].startswith("v36_comparison_panel_")
    assert first["preregistrationHash"].startswith("v36_preregistration_")


def test_preregistration_rejects_incomplete_comparison_panel() -> None:
    panel = _panel()
    panel.pop("benchmarkPolicyHash")

    try:
        build_preregistration(
            registry=_registry(),
            campaign_id="v36-bounded-smoke",
            created_at="2026-07-19T00:00:00Z",
            comparison_panel=panel,
        )
    except ValueError as error:
        assert str(error) == "comparison_panel_incomplete:benchmarkPolicyHash"
    else:
        raise AssertionError("incomplete comparison panel must fail closed")
