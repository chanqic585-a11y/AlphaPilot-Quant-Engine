from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphapilot.automatic_candidate_research.executor import (
    AutomaticCandidateResearchExecutor,
)
from alphapilot.automatic_candidate_research.preregistration import (
    build_preregistration,
)
from alphapilot.research_service import (
    ResearchService,
    ResearchServicePolicy,
    ResearchServiceStateStore,
)
from alphapilot.standard_replication import ReplicationSourceRegistry


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "research/source_registry/strategy_research_source_registry.json"


def test_executor_writes_complete_zero_winner_artifact_set(tmp_path: Path) -> None:
    registry = ReplicationSourceRegistry.load(REGISTRY_PATH)
    campaign_input = _campaign_input(registry=registry, campaign_id="v36-zero")
    executor = AutomaticCandidateResearchExecutor(
        registry=registry,
        output_root=tmp_path / "reports",
        campaign_inputs={"v36-zero": campaign_input},
    )

    result = executor.execute(_job(registry, "v36-zero"))

    assert result["status"] == "research_blocked_data"
    assert result["candidateCount"] == 9
    assert result["blockedFamilyCount"] == 2
    assert result["formalRunCount"] == 0
    assert result["resultReadCount"] == 0
    assert result["lockedOosReadCount"] == 0
    assert result["releaseCount"] == 0
    assert result["demoArm"] is False
    assert result["orderCount"] == 0
    campaign_root = tmp_path / "reports/v36-zero"
    assert {path.name for path in campaign_root.glob("*.json")} == {
        "preregistration.json",
        "development_replay_audit.json",
        "development_projection.json",
        "neighborhood_selection.json",
        "formal_route.json",
        "immutable_releases.json",
        "campaign_summary.json",
        "artifact_manifest.json",
    }
    manifest = json.loads((campaign_root / "artifact_manifest.json").read_text("utf-8"))
    assert len(manifest["artifacts"]) == 7
    assert all(item["sha256"] for item in manifest["artifacts"])


def test_executor_honors_pause_at_a_safe_stage_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = ReplicationSourceRegistry.load(REGISTRY_PATH)
    campaign_input = _campaign_input(registry=registry, campaign_id="v56-safe-pause")
    pause_file = tmp_path / "PAUSE"
    from alphapilot.automatic_candidate_research import executor as executor_module

    original = executor_module.build_preregistration

    def build_then_pause(**kwargs):
        result = original(**kwargs)
        pause_file.write_text("paused\n", encoding="ascii")
        return result

    monkeypatch.setattr(executor_module, "build_preregistration", build_then_pause)
    executor = AutomaticCandidateResearchExecutor(
        registry=registry,
        output_root=tmp_path / "reports",
        campaign_inputs={"v56-safe-pause": campaign_input},
        pause_file=pause_file,
    )

    result = executor.execute(_job(registry, "v56-safe-pause"))

    assert result["status"] == "paused"
    assert result["campaignId"] == "v56-safe-pause"
    assert result["pausedStage"] == "preregistration"
    assert result["formalRunCount"] == 0
    assert result["lockedOosReadCount"] == 0
    assert result["releaseCount"] == 0
    assert result["demoArm"] is False
    assert result["orderCount"] == 0
    assert not (tmp_path / "reports/v56-safe-pause").exists()


def test_executor_integrates_with_v35_service_without_execution_side_effects(
    tmp_path: Path,
) -> None:
    registry = ReplicationSourceRegistry.load(REGISTRY_PATH)
    campaign_input = _campaign_input(registry=registry, campaign_id="v36-formal")
    preregistration = build_preregistration(
        registry=registry,
        campaign_id="v36-formal",
        created_at=str(campaign_input["createdAt"]),
        comparison_panel=campaign_input["comparisonPanel"],
    )
    trials = preregistration["trialsByCandidate"]["v35_tsmom_source_replication"]
    campaign_input["developmentEvidence"] = [
        _directional_evidence(trial) for trial in trials
    ]
    campaign_input["formalOutcomes"] = [
        {
            "candidateId": "v35_tsmom_source_replication",
            "trialId": trials[1]["trialId"],
            "comparisonPanelHash": preregistration["comparisonPanelHash"],
            "formalArtifactHash": "synthetic-formal-fixture-hash",
            "outcome": "formal_pass",
            "lockedOosReadCount": 1,
        }
    ]
    executor = AutomaticCandidateResearchExecutor(
        registry=registry,
        output_root=tmp_path / "reports",
        campaign_inputs={"v36-formal": campaign_input},
    )
    policy = ResearchServicePolicy.default()
    service = ResearchService(
        policy=policy,
        state_store=ResearchServiceStateStore(tmp_path / "state.json", policy=policy),
        executor=executor,
        lease_path=tmp_path / "service.lock",
        receipt_path=tmp_path / "receipts.jsonl",
        owner="v36-test",
    )
    service.enqueue(
        campaign_id="v36-formal",
        family_ids=registry.family_ids,
        candidate_ids=tuple(preregistration["candidateIds"]),
        queued_at="2026-07-19T00:00:00Z",
    )

    receipt = service.run_cycle(now="2026-07-19T00:01:00Z")

    assert receipt["status"] == "waiting_exact_release_approval"
    assert receipt["releaseCount"] == 1
    assert receipt["formalRunCount"] == 1
    assert receipt["resultReadCount"] == 1
    assert receipt["lockedOosReadCount"] == 1
    assert receipt["demoArm"] is False
    assert receipt["orderCount"] == 0


def _campaign_input(
    *, registry: ReplicationSourceRegistry, campaign_id: str
) -> dict[str, object]:
    return {
        "campaignId": campaign_id,
        "createdAt": "2026-07-19T00:00:00Z",
        "familyIds": list(registry.family_ids),
        "candidateIds": sorted(
            variant.candidate_id
            for family in registry.items
            for variant in family.variants
        ),
        "comparisonPanel": {
            "developmentStart": "2024-01-01T00:00:00Z",
            "developmentEnd": "2025-01-01T00:00:00Z",
            "dataSnapshotId": "okx-public-snapshot-v34c",
            "costPolicyHash": "cost-policy-v13",
            "capitalPolicyHash": "capital-policy-v18",
            "benchmarkPolicyHash": "benchmark-policy-v32",
            "randomSeed": 36,
        },
        "developmentEvidence": [],
        "formalOutcomes": [],
    }


def _job(registry: ReplicationSourceRegistry, campaign_id: str) -> dict[str, object]:
    return {
        "campaignId": campaign_id,
        "familyIds": list(registry.family_ids),
        "candidateIds": sorted(
            variant.candidate_id
            for family in registry.items
            for variant in family.variants
        ),
    }


def _directional_evidence(trial: dict[str, object]) -> dict[str, object]:
    trial_index = int(trial["trialIndex"])
    return {
        "candidateId": trial["candidateId"],
        "trialId": trial["trialId"],
        "trialIndex": trial_index,
        "strategyType": "directional",
        "split": "development",
        "metrics": {
            "eventCount": 40,
            "profitFactor": (1.20, 1.25, 1.23)[trial_index],
            "averageNetR": (0.07, 0.09, 0.08)[trial_index],
            "totalNetR": 3.0,
            "mfe": 0.9,
            "mae": -0.4,
            "totalCostR": 0.4,
            "benchmarkIncrementNetR": 1.0,
            "maxDrawdownR": (1.1, 1.2, 1.15)[trial_index],
            "concentration": 0.2,
        },
    }
