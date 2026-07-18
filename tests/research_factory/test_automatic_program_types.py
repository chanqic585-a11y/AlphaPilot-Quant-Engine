from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from alphapilot.research_factory.artifact_paths import ProgramArtifactPaths
from alphapilot.research_factory.program_types import (
    PROGRAM_STAGES,
    TERMINAL_ROUTES,
    ProgramBudget,
    ProgramState,
    build_program_id,
)


def test_program_budget_uses_frozen_workflow_limits() -> None:
    budget = ProgramBudget()

    assert budget.to_dict() == {
        "maximumResearchCampaigns": 3,
        "maximumFamiliesPerCampaign": 8,
        "maximumInitialVariantsPerFamily": 2,
        "maximumInitialCandidatesPerCampaign": 16,
        "maximumStructuralRevisionPerFamily": 1,
        "maximumFormalCandidatesPerCampaign": 6,
        "maximumFullBacktestsPerCampaign": 48,
        "maximumFullBacktestsAcrossProgram": 144,
        "maximumDemoReleasesPerCampaign": 3,
    }
    with pytest.raises(FrozenInstanceError):
        budget.maximum_research_campaigns = 4  # type: ignore[misc]


def test_program_id_is_canonical_and_input_sensitive() -> None:
    first = build_program_id(
        baseline_commit="f9f36f4",
        program_spec_hash="program_spec_abc",
    )
    second = build_program_id(
        baseline_commit="f9f36f4",
        program_spec_hash="program_spec_abc",
    )
    changed = build_program_id(
        baseline_commit="f9f36f4",
        program_spec_hash="program_spec_def",
    )

    assert first == second
    assert first.startswith("automatic_strategy_demo_")
    assert first != changed


def test_program_state_rejects_unknown_stage_and_route() -> None:
    with pytest.raises(ValueError, match="unknown program stage"):
        ProgramState.create(
            program_id="automatic_strategy_demo_test",
            baseline_commit="f9f36f4",
            program_spec_hash="program_spec_abc",
            created_at="2026-07-18T00:00:00Z",
            stage="invented_stage",
        )

    state = ProgramState.create(
        program_id="automatic_strategy_demo_test",
        baseline_commit="f9f36f4",
        program_spec_hash="program_spec_abc",
        created_at="2026-07-18T00:00:00Z",
    )
    with pytest.raises(ValueError, match="unknown terminal route"):
        state.transition(
            stage="blocked",
            updated_at="2026-07-18T00:01:00Z",
            terminal_route="made_up_route",
        )

    assert "program_created" in PROGRAM_STAGES
    assert "blocked_waiting_exact_release_approval" in TERMINAL_ROUTES


def test_program_state_serializes_resume_counters() -> None:
    state = ProgramState.create(
        program_id="automatic_strategy_demo_test",
        baseline_commit="f9f36f4",
        program_spec_hash="program_spec_abc",
        created_at="2026-07-18T00:00:00Z",
    ).transition(
        stage="data_capability_ready",
        updated_at="2026-07-18T00:01:00Z",
        previous_checkpoint="baseline_frozen",
        next_allowed_stage="hypotheses_frozen",
        one_shot_claims_consumed=0,
        result_read_count=0,
    )

    payload = state.to_dict()
    assert payload["previousCheckpoint"] == "baseline_frozen"
    assert payload["nextAllowedStage"] == "hypotheses_frozen"
    assert payload["oneShotClaimsConsumed"] == 0
    assert payload["resultReadCount"] == 0


def test_artifact_paths_are_program_campaign_and_candidate_scoped(tmp_path: Path) -> None:
    paths = ProgramArtifactPaths(tmp_path, "automatic_strategy_demo_test")

    assert paths.program_root == (
        tmp_path / "automatic_research_program" / "automatic_strategy_demo_test"
    )
    assert paths.checkpoint("v19") == paths.program_root / "checkpoints" / "v19.json"
    assert paths.campaign("campaign_01") == paths.program_root / "campaigns" / "campaign_01"
    assert paths.candidate("campaign_01", "candidate_01") == (
        paths.program_root / "campaigns" / "campaign_01" / "candidates" / "candidate_01"
    )
    with pytest.raises(ValueError, match="unsafe path component"):
        paths.candidate("campaign_01", "../escape")
