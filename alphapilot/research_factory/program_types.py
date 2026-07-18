"""Frozen contracts for the V19-V24 automatic research program."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


PROGRAM_STAGES = frozenset(
    {
        "program_created",
        "baseline_frozen",
        "data_capability_ready",
        "hypotheses_frozen",
        "candidates_certified",
        "prefilter_completed",
        "formal_campaign_frozen",
        "formal_validation_completed",
        "release_ready",
        "demo_waiting_approval",
        "demo_armed",
        "completed",
        "blocked",
    }
)

TERMINAL_ROUTES = frozenset(
    {
        "completed_demo_admission",
        "completed_research_forward_demo_admission",
        "completed_zero_qualified_candidates",
        "blocked_data_capability",
        "blocked_remote_freeze",
        "blocked_formal_engine",
        "blocked_demo_environment",
        "blocked_waiting_exact_release_approval",
    }
)


@dataclass(frozen=True)
class ProgramBudget:
    maximum_research_campaigns: int = 3
    maximum_families_per_campaign: int = 8
    maximum_initial_variants_per_family: int = 2
    maximum_initial_candidates_per_campaign: int = 16
    maximum_structural_revision_per_family: int = 1
    maximum_formal_candidates_per_campaign: int = 6
    maximum_full_backtests_per_campaign: int = 48
    maximum_full_backtests_across_program: int = 144
    maximum_demo_releases_per_campaign: int = 3

    def __post_init__(self) -> None:
        values = self.to_dict().values()
        if any(not isinstance(value, int) or value < 0 for value in values):
            raise ValueError("program budget values must be non-negative integers")
        if self.maximum_initial_candidates_per_campaign > (
            self.maximum_families_per_campaign * self.maximum_initial_variants_per_family
        ):
            raise ValueError("candidate budget exceeds family and variant bounds")
        if self.maximum_demo_releases_per_campaign > 3:
            raise ValueError("maximumDemoReleasesPerCampaign cannot exceed 3")

    def to_dict(self) -> dict[str, int]:
        return {
            "maximumResearchCampaigns": self.maximum_research_campaigns,
            "maximumFamiliesPerCampaign": self.maximum_families_per_campaign,
            "maximumInitialVariantsPerFamily": self.maximum_initial_variants_per_family,
            "maximumInitialCandidatesPerCampaign": self.maximum_initial_candidates_per_campaign,
            "maximumStructuralRevisionPerFamily": self.maximum_structural_revision_per_family,
            "maximumFormalCandidatesPerCampaign": self.maximum_formal_candidates_per_campaign,
            "maximumFullBacktestsPerCampaign": self.maximum_full_backtests_per_campaign,
            "maximumFullBacktestsAcrossProgram": self.maximum_full_backtests_across_program,
            "maximumDemoReleasesPerCampaign": self.maximum_demo_releases_per_campaign,
        }


def build_program_id(*, baseline_commit: str, program_spec_hash: str) -> str:
    if not baseline_commit.strip() or not program_spec_hash.strip():
        raise ValueError("baseline commit and program spec hash are required")
    digest = stable_hash(
        {
            "baselineCommit": baseline_commit.strip(),
            "programSpecHash": program_spec_hash.strip(),
            "workflowVersion": "v13.27.1.19-24",
        }
    )
    return f"automatic_strategy_demo_{digest[:16]}"


@dataclass(frozen=True)
class ProgramState:
    program_id: str
    baseline_commit: str
    program_spec_hash: str
    stage: str
    stage_attempt: int
    active_campaign_index: int
    active_campaign_id: str | None
    previous_checkpoint: str | None
    next_allowed_stage: str | None
    one_shot_claims_consumed: int
    result_read_count: int
    terminal_route: str | None
    human_gate_status: str
    created_at: str
    updated_at: str
    schema_version: str = "automatic_strategy_demo_program_state_v1"

    def __post_init__(self) -> None:
        if self.stage not in PROGRAM_STAGES:
            raise ValueError(f"unknown program stage: {self.stage}")
        if self.terminal_route is not None and self.terminal_route not in TERMINAL_ROUTES:
            raise ValueError(f"unknown terminal route: {self.terminal_route}")
        if self.stage_attempt < 0 or self.active_campaign_index < 0:
            raise ValueError("stage and campaign counters must be non-negative")
        if self.one_shot_claims_consumed < 0 or self.result_read_count < 0:
            raise ValueError("formal counters must be non-negative")

    @classmethod
    def create(
        cls,
        *,
        program_id: str,
        baseline_commit: str,
        program_spec_hash: str,
        created_at: str,
        stage: str = "program_created",
    ) -> "ProgramState":
        return cls(
            program_id=program_id,
            baseline_commit=baseline_commit,
            program_spec_hash=program_spec_hash,
            stage=stage,
            stage_attempt=0,
            active_campaign_index=0,
            active_campaign_id=None,
            previous_checkpoint=None,
            next_allowed_stage="baseline_frozen" if stage == "program_created" else None,
            one_shot_claims_consumed=0,
            result_read_count=0,
            terminal_route=None,
            human_gate_status="not_requested",
            created_at=created_at,
            updated_at=created_at,
        )

    def transition(self, *, stage: str, updated_at: str, **changes: Any) -> "ProgramState":
        if stage not in PROGRAM_STAGES:
            raise ValueError(f"unknown program stage: {stage}")
        if "terminal_route" in changes:
            route = changes["terminal_route"]
            if route is not None and route not in TERMINAL_ROUTES:
                raise ValueError(f"unknown terminal route: {route}")
        return replace(self, stage=stage, updated_at=updated_at, **changes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "programId": self.program_id,
            "baselineCommit": self.baseline_commit,
            "programSpecHash": self.program_spec_hash,
            "stage": self.stage,
            "stageAttempt": self.stage_attempt,
            "activeCampaignIndex": self.active_campaign_index,
            "activeCampaignId": self.active_campaign_id,
            "previousCheckpoint": self.previous_checkpoint,
            "nextAllowedStage": self.next_allowed_stage,
            "oneShotClaimsConsumed": self.one_shot_claims_consumed,
            "resultReadCount": self.result_read_count,
            "terminalRoute": self.terminal_route,
            "humanGateStatus": self.human_gate_status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


def program_state_from_dict(payload: dict[str, Any]) -> ProgramState:
    return ProgramState(
        program_id=str(payload["programId"]),
        baseline_commit=str(payload["baselineCommit"]),
        program_spec_hash=str(payload["programSpecHash"]),
        stage=str(payload["stage"]),
        stage_attempt=int(payload.get("stageAttempt", 0)),
        active_campaign_index=int(payload.get("activeCampaignIndex", 0)),
        active_campaign_id=payload.get("activeCampaignId"),
        previous_checkpoint=payload.get("previousCheckpoint"),
        next_allowed_stage=payload.get("nextAllowedStage"),
        one_shot_claims_consumed=int(payload.get("oneShotClaimsConsumed", 0)),
        result_read_count=int(payload.get("resultReadCount", 0)),
        terminal_route=payload.get("terminalRoute"),
        human_gate_status=str(payload.get("humanGateStatus", "not_requested")),
        created_at=str(payload["createdAt"]),
        updated_at=str(payload["updatedAt"]),
        schema_version=str(payload.get("schemaVersion", "automatic_strategy_demo_program_state_v1")),
    )
