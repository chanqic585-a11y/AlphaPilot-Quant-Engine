from __future__ import annotations

import json
from pathlib import Path

from alphapilot.research_factory.artifact_paths import ProgramArtifactPaths
from alphapilot.research_factory.program_state import ProgramStateStore
from alphapilot.research_factory.program_types import ProgramState
from alphapilot.research_factory.program_v23 import (
    build_release_plan,
    run_v23_release_generation,
)


def test_capital_infeasible_candidate_produces_zero_release_route() -> None:
    plan = build_release_plan(
        campaign_id="campaign-a",
        candidate_results=[
            {
                "candidateId": "candidate-a",
                "status": "capital_infeasible",
                "releaseEligible": False,
            }
        ],
        maximum_release_count=3,
    )

    assert plan["releaseCount"] == 0
    assert plan["releaseHashes"] == []
    assert plan["terminalRoute"] == "completed_zero_qualified_candidates"
    assert plan["approvalRequired"] is False


def test_research_forward_candidate_never_auto_approves() -> None:
    plan = build_release_plan(
        campaign_id="campaign-a",
        candidate_results=[
            {
                "candidateId": "candidate-b",
                "status": "research_pass_no_clean_holdout",
                "releaseEligible": True,
                "rankingScore": 1.0,
            }
        ],
        maximum_release_count=3,
    )

    assert plan["releaseCount"] == 1
    assert plan["releases"][0]["releaseClass"] == "research_forward"
    assert plan["releases"][0]["approved"] is False
    assert plan["approvalRequired"] is True


def test_only_eligible_statuses_create_releases_and_campaign_cap_is_enforced() -> None:
    results = [
        {
            "candidateId": f"candidate-{index}",
            "status": "formal_pass",
            "releaseEligible": True,
            "rankingScore": float(index),
        }
        for index in range(5)
    ]
    results.append(
        {
            "candidateId": "candidate-ineligible",
            "status": "formal_economic_failed",
            "releaseEligible": False,
            "rankingScore": 999.0,
        }
    )

    plan = build_release_plan(
        campaign_id="campaign-a",
        candidate_results=results,
        maximum_release_count=3,
    )

    assert plan["releaseCount"] == 3
    assert [row["candidateId"] for row in plan["releases"]] == [
        "candidate-4",
        "candidate-3",
        "candidate-2",
    ]


def test_release_hash_and_research_forward_overlay_are_deterministic() -> None:
    candidate = {
        "candidateId": "candidate-b",
        "status": "research_pass_funding_unavailable",
        "releaseEligible": True,
        "rankingScore": 2.0,
        "strategyId": "strategy-b",
        "familyId": "family-b",
        "strategyDefinitionHash": "strategy-hash",
        "exitPolicyHash": "exit-hash",
    }

    first = build_release_plan(
        campaign_id="campaign-a",
        candidate_results=[candidate],
        maximum_release_count=3,
    )["releases"][0]
    second = build_release_plan(
        campaign_id="campaign-a",
        candidate_results=[candidate],
        maximum_release_count=3,
    )["releases"][0]

    assert first["releaseHash"] == second["releaseHash"]
    assert first["riskOverlay"]["maximumConcurrentPositions"] == 1
    assert first["riskOverlay"]["maximumOpenRiskPctEquity"] == 0.10
    assert first["riskOverlay"]["addingAllowed"] is False
    assert first["riskOverlay"]["averagingAllowed"] is False
    assert first["riskOverlay"]["martingaleAllowed"] is False
    assert first["riskOverlayHash"]


def test_v23_runner_freezes_zero_release_route_and_resumes(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    program_id = "program-a"
    campaign_id = "campaign-a"
    paths = ProgramArtifactPaths(reports, program_id)
    store = ProgramStateStore(paths)
    state = ProgramState.create(
        program_id=program_id,
        baseline_commit="abc123",
        program_spec_hash="spec123",
        created_at="2026-07-18T00:00:00Z",
    ).transition(
        stage="formal_validation_completed",
        updated_at="2026-07-18T00:00:00Z",
        active_campaign_id=campaign_id,
        one_shot_claims_consumed=1,
        result_read_count=1,
    )
    store.save(state)
    candidate_root = reports / "formal_validation" / campaign_id / "candidate-a"
    candidate_root.mkdir(parents=True)
    (candidate_root / "formal_route.json").write_text(
        json.dumps(
            {
                "candidateId": "candidate-a",
                "status": "capital_infeasible",
                "releaseEligible": False,
            }
        ),
        encoding="utf-8",
    )
    (candidate_root / "artifact_manifest.json").write_text(
        json.dumps({"manifestHash": "manifest-a"}), encoding="utf-8"
    )
    store.write_checkpoint(
        stage="v22",
        created_at="2026-07-18T00:00:00Z",
        payload={"artifactRoot": candidate_root.as_posix()},
    )

    result = run_v23_release_generation(
        reports_root=reports,
        program_id=program_id,
        generated_at="2026-07-18T01:00:00Z",
    )
    resumed = run_v23_release_generation(
        reports_root=reports,
        program_id=program_id,
        generated_at="2026-07-18T01:00:00Z",
    )

    assert result["releaseCount"] == 0
    assert result["terminalRoute"] == "completed_zero_qualified_candidates"
    assert store.load().stage == "release_ready"
    assert json.loads((paths.program_root / "zero_release_route.json").read_text())["demoArm"] is False
    assert resumed["resumed"] is True
