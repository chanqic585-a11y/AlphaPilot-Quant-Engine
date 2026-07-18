"""Bounded and resumable V28-V32 research-renewal orchestration."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash

from .artifact_paths import ProgramArtifactPaths
from .okx_release_admission import (
    build_immutable_release,
    build_release_approval_request,
)
from .program_ledger import ProgramLedger


PARENT_PROGRAM_ID = "automatic_strategy_to_demo_v26_2aff44adf84d039c"
_TERMINAL_ROUTES = {
    "completed_zero_qualified_candidates",
    "blocked_formal_data",
    "blocked_okx_data",
    "blocked_okx_portability",
    "blocked_waiting_exact_release_approval",
    "implementation_invalid",
}
_PASS_CLASSES = {
    "formal_pass",
    "research_pass_no_clean_holdout",
    "research_pass_funding_unavailable",
}
_KNOWN_RESULT_CLASSES = _PASS_CLASSES | {
    "formal_economic_failed",
    "statistical_failed",
    "capital_infeasible",
    "implementation_invalid",
    "formal_data_blocked",
}


@dataclass(frozen=True)
class ResearchRenewalBudget:
    maximum_campaigns: int = 2
    maximum_families_per_campaign: int = 6
    maximum_initial_variants_per_family: int = 2
    maximum_initial_candidates_per_campaign: int = 12
    maximum_structural_revisions_per_family: int = 1
    maximum_formal_candidates_per_campaign: int = 4
    maximum_full_backtests_per_campaign: int = 48
    maximum_additional_full_backtests: int = 96
    maximum_demo_releases_per_campaign: int = 3

    def to_dict(self) -> dict[str, int]:
        return {
            "maximumCampaigns": self.maximum_campaigns,
            "maximumFamiliesPerCampaign": self.maximum_families_per_campaign,
            "maximumInitialVariantsPerFamily": self.maximum_initial_variants_per_family,
            "maximumInitialCandidatesPerCampaign": self.maximum_initial_candidates_per_campaign,
            "maximumStructuralRevisionsPerFamily": self.maximum_structural_revisions_per_family,
            "maximumFormalCandidatesPerCampaign": self.maximum_formal_candidates_per_campaign,
            "maximumFullBacktestsPerCampaign": self.maximum_full_backtests_per_campaign,
            "maximumAdditionalFullBacktests": self.maximum_additional_full_backtests,
            "maximumDemoReleasesPerCampaign": self.maximum_demo_releases_per_campaign,
        }


def build_research_renewal_program_id(prompt_hash: str) -> str:
    normalized = str(prompt_hash or "").strip()
    if not normalized:
        raise ValueError("prompt_hash_missing")
    identity = {
        "schemaVersion": "automatic_strategy_renewal_identity_v1",
        "parentProgramId": PARENT_PROGRAM_ID,
        "promptHash": normalized,
        "versionRange": "v13.27.1.28-v13.27.1.32",
    }
    digest = stable_hash(identity, prefix="automatic_strategy_renewal_v28")
    return f"automatic_strategy_renewal_v28_{digest[-16:]}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest(root: Path) -> dict[str, Any]:
    artifacts = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256(path),
            "sizeBytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    payload: dict[str, Any] = {
        "schemaVersion": "automatic_strategy_renewal_artifact_manifest_v1",
        "artifactCount": len(artifacts),
        "artifacts": artifacts,
    }
    payload["manifestHash"] = stable_hash(
        payload, prefix="automatic_strategy_renewal_manifest"
    )
    return payload


def refresh_artifact_manifest(*, reports_root: Path, program_id: str) -> dict[str, Any]:
    paths = ProgramArtifactPaths(Path(reports_root), program_id)
    manifest = _manifest(paths.program_root)
    write_json_atomic(paths.artifact_manifest, manifest)
    return manifest


def _write_markdown(path: Path, title: str, rows: Sequence[tuple[str, Any]]) -> None:
    lines = [f"# {title}", ""]
    lines.extend(f"- **{name}:** {value}" for name, value in rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _candidate_result(
    candidate: Mapping[str, Any], *, campaign_id: str
) -> dict[str, Any]:
    candidate_id = str(candidate.get("candidateId") or "").strip()
    family_id = str(candidate.get("familyId") or "").strip()
    strategy_type = str(candidate.get("strategyType") or "").strip()
    candidate_hash = str(candidate.get("candidateHash") or "").strip()
    if not all((candidate_id, family_id, strategy_type, candidate_hash)):
        raise ValueError("candidate_identity_incomplete")
    formal_status = str(candidate.get("formalStatus") or "formal_data_blocked")
    if formal_status not in _KNOWN_RESULT_CLASSES:
        raise ValueError(f"unknown_formal_result_class:{formal_status}")
    full_backtests = int(candidate.get("fullBacktestsUsed") or 0)
    if full_backtests < 0:
        raise ValueError("negative_full_backtest_count")
    release_eligible = bool(candidate.get("releaseEligible") is True)
    if release_eligible and formal_status not in _PASS_CLASSES:
        raise ValueError("release_eligibility_without_pass")
    payload: dict[str, Any] = {
        "schemaVersion": "research_renewal_candidate_result_v1",
        "campaignId": campaign_id,
        "candidateId": candidate_id,
        "candidateHash": candidate_hash,
        "familyId": family_id,
        "strategyType": strategy_type,
        "revisionOfCandidateId": candidate.get("revisionOfCandidateId"),
        "prefilterStatus": str(candidate.get("prefilterStatus") or "not_run"),
        "formalStatus": formal_status,
        "fullBacktestsUsed": full_backtests,
        "releaseEligible": release_eligible,
        "approved": False,
        "demoArm": False,
        "orderCount": 0,
    }
    payload["resultHash"] = stable_hash(payload, prefix="renewal_candidate_result")
    return payload


def run_research_renewal_program(
    *,
    reports_root: Path,
    prompt_hash: str,
    implementation_commit: str,
    generated_at: str,
    campaigns: Sequence[Mapping[str, Any]],
    baseline_merge_commits: Mapping[str, str] | None = None,
    eligibility_window_policy_hash: str | None = None,
    benchmark_comparability_policy_hash: str | None = None,
    budget: ResearchRenewalBudget | None = None,
) -> dict[str, Any]:
    """Run a preregistered campaign bundle without altering any candidate."""

    active_budget = budget or ResearchRenewalBudget()
    if len(campaigns) > active_budget.maximum_campaigns:
        raise ValueError("campaign_budget_exceeded")
    program_id = build_research_renewal_program_id(prompt_hash)
    paths = ProgramArtifactPaths(Path(reports_root), program_id)
    root = paths.program_root
    summary_path = root / "program_summary.json"
    if summary_path.is_file():
        return json.loads(summary_path.read_text(encoding="utf-8"))

    program_spec: dict[str, Any] = {
        "schemaVersion": "automatic_strategy_renewal_program_spec_v1",
        "programId": program_id,
        "parentProgramId": PARENT_PROGRAM_ID,
        "promptHash": prompt_hash,
        "implementationCommit": implementation_commit,
        "baselineMergeCommits": dict(baseline_merge_commits or {}),
        "historicalMutationCount": 0,
        "budget": active_budget.to_dict(),
        "candidateEditsAfterResultsAllowed": False,
        "automaticApprovalAllowed": False,
        "demoArm": False,
        "orderCount": 0,
    }
    program_spec["programSpecHash"] = stable_hash(
        program_spec, prefix="automatic_strategy_renewal_spec"
    )
    write_json_atomic(root / "program_spec.json", program_spec)
    ledger = ProgramLedger(paths.ledger)
    ledger.append(
        event_type="program_initialized",
        stage="v28_data_contracts",
        created_at=generated_at,
        payload={
            "programId": program_id,
            "programSpecHash": program_spec["programSpecHash"],
        },
    )

    failed_candidate_ids: set[str] = set()
    revisions_by_family: Counter[str] = Counter()
    families_by_type: dict[str, set[str]] = defaultdict(set)
    candidate_count = 0
    archived_count = 0
    prefilter_survivor_count = 0
    formal_candidate_count = 0
    formal_pass_count = 0
    research_pass_count = 0
    full_backtests_used = 0
    campaign_count = 0
    structural_revision_count = 0
    result_read_count = 0
    formal_run_count = 0
    release_eligible_ids: list[str] = []
    release_eligible_candidates: list[tuple[str, dict[str, Any], str]] = []
    data_blocked = False

    for campaign in campaigns:
        campaign_id = str(campaign.get("campaignId") or "").strip()
        if not campaign_id:
            raise ValueError("campaign_id_missing")
        campaign_count += 1
        campaign_status = str(campaign.get("status") or "ready")
        if campaign_status == "formal_data_blocked":
            data_blocked = True
        rows = list(campaign.get("candidates") or [])
        if len(rows) > active_budget.maximum_initial_candidates_per_campaign:
            raise ValueError("initial_candidate_budget_exceeded")
        families = {str(row.get("familyId") or "") for row in rows}
        if len(families) > active_budget.maximum_families_per_campaign:
            raise ValueError("campaign_family_budget_exceeded")
        variant_counts = Counter(str(row.get("familyId") or "") for row in rows)
        for family_id, count in variant_counts.items():
            revisions = sum(
                1
                for row in rows
                if str(row.get("familyId") or "") == family_id
                and row.get("revisionOfCandidateId")
            )
            initial_count = count - revisions
            if initial_count > active_budget.maximum_initial_variants_per_family:
                raise ValueError("initial_variant_budget_exceeded")

        campaign_backtests = 0
        campaign_formal = 0
        campaign_archived = 0
        campaign_release_eligible: list[str] = []
        for raw_candidate in rows:
            candidate = dict(raw_candidate)
            candidate_id = str(candidate.get("candidateId") or "").strip()
            family_id = str(candidate.get("familyId") or "").strip()
            if candidate_id in failed_candidate_ids:
                raise ValueError("failed_candidate_identity_reused")
            revision_of = str(candidate.get("revisionOfCandidateId") or "").strip()
            if revision_of:
                revisions_by_family[family_id] += 1
                structural_revision_count += 1
                if (
                    revisions_by_family[family_id]
                    > active_budget.maximum_structural_revisions_per_family
                ):
                    raise ValueError("structural_revision_budget_exceeded")
                if revision_of not in failed_candidate_ids:
                    raise ValueError("revision_parent_not_archived")

            result = _candidate_result(candidate, campaign_id=campaign_id)
            candidate_count += 1
            strategy_type = str(result["strategyType"])
            families_by_type[strategy_type].add(family_id)
            used = int(result["fullBacktestsUsed"])
            campaign_backtests += used
            full_backtests_used += used
            if campaign_backtests > active_budget.maximum_full_backtests_per_campaign:
                raise ValueError("campaign_full_backtest_budget_exceeded")
            if full_backtests_used > active_budget.maximum_additional_full_backtests:
                raise ValueError("additional_full_backtest_budget_exceeded")
            if result["prefilterStatus"] == "passed":
                prefilter_survivor_count += 1
            if result["formalStatus"] != "formal_data_blocked":
                campaign_formal += 1
                formal_candidate_count += 1
                formal_run_count += 1
                result_read_count += 1
            if campaign_formal > active_budget.maximum_formal_candidates_per_campaign:
                raise ValueError("campaign_formal_candidate_budget_exceeded")
            if result["formalStatus"] == "formal_pass":
                formal_pass_count += 1
            elif result["formalStatus"] in {
                "research_pass_no_clean_holdout",
                "research_pass_funding_unavailable",
            }:
                research_pass_count += 1
            if result["releaseEligible"]:
                release_eligible_ids.append(candidate_id)
                campaign_release_eligible.append(candidate_id)
                release_eligible_candidates.append(
                    (campaign_id, candidate, str(result["formalStatus"]))
                )
            else:
                failed_candidate_ids.add(candidate_id)
                archived_count += 1
                campaign_archived += 1

            candidate_root = paths.candidate(campaign_id, candidate_id)
            write_json_atomic(candidate_root / "candidate_result.json", result)

        campaign_summary: dict[str, Any] = {
            "schemaVersion": "research_renewal_campaign_summary_v1",
            "campaignId": campaign_id,
            "status": campaign_status,
            "candidateCount": len(rows),
            "familyCount": len(families),
            "formalCandidateCount": campaign_formal,
            "archivedCount": campaign_archived,
            "fullBacktestsUsed": campaign_backtests,
            "releaseEligibleCandidateIds": campaign_release_eligible,
        }
        campaign_summary["summaryHash"] = stable_hash(
            campaign_summary, prefix="research_renewal_campaign"
        )
        campaign_root = paths.campaign(campaign_id)
        write_json_atomic(campaign_root / "campaign_summary.json", campaign_summary)
        _write_markdown(
            campaign_root / "campaign_summary.md",
            f"Research Renewal Campaign {campaign_id}",
            [
                ("Status", campaign_status),
                ("Candidates", len(rows)),
                ("Formal candidates", campaign_formal),
                ("Archived", campaign_archived),
                ("Release eligible", len(campaign_release_eligible)),
            ],
        )
        ledger.append(
            event_type="campaign_completed",
            stage="v30_formal_validation",
            created_at=generated_at,
            payload={
                "campaignId": campaign_id,
                "campaignSummaryHash": campaign_summary["summaryHash"],
            },
        )
        if release_eligible_ids:
            break

    releases: list[dict[str, Any]] = []
    approval_requests: list[dict[str, Any]] = []
    release_blockers: list[str] = []
    releases_by_campaign: Counter[str] = Counter()
    for campaign_id, candidate, result_class in release_eligible_candidates:
        okx_profile = candidate.get("okxProfile")
        portability_audit = candidate.get("portabilityAudit")
        if not isinstance(okx_profile, Mapping):
            okx_profile = None
        if not isinstance(portability_audit, Mapping):
            portability_audit = None
        okx_ready = okx_profile is not None and okx_profile.get("status") == "ready"
        portability_ready = (
            portability_audit is not None
            and portability_audit.get("status") == "passed"
        )
        if not (okx_ready or portability_ready):
            if (
                portability_audit is not None
                and portability_audit.get("status") == "blocked_okx_portability"
            ):
                release_blockers.append("blocked_okx_portability")
            else:
                release_blockers.append("blocked_okx_data")
            continue
        releases_by_campaign[campaign_id] += 1
        if (
            releases_by_campaign[campaign_id]
            > active_budget.maximum_demo_releases_per_campaign
        ):
            raise ValueError("campaign_demo_release_budget_exceeded")
        release = build_immutable_release(
            campaign_id=campaign_id,
            candidate=candidate,
            result_class=result_class,
            okx_profile=okx_profile,
            portability_audit=portability_audit,
            evidence_summary=dict(candidate.get("evidenceSummary") or {}),
            risk_overlay=dict(candidate.get("riskOverlay") or {}),
        )
        request = build_release_approval_request(release)
        candidate_root = paths.candidate(
            campaign_id, str(candidate.get("candidateId") or "")
        )
        write_json_atomic(candidate_root / "immutable_demo_release.json", release)
        write_json_atomic(candidate_root / "demo_approval_request.json", request)
        _write_markdown(
            candidate_root / "demo_approval_request.md",
            "Exact Demo Release Approval Required",
            [
                ("Release ID", release["releaseId"]),
                ("Release Hash", release["releaseHash"]),
                ("Candidate ID", release["candidateId"]),
                ("Evidence Class", release["resultClass"]),
                ("Admission route", release["admissionRoute"]),
                ("Risk Overlay Hash", release["riskOverlayHash"]),
                ("Status", request["status"]),
                ("Demo ARM", False),
                ("Orders", 0),
            ],
        )
        releases.append(release)
        approval_requests.append(request)

    if releases:
        final_route = "blocked_waiting_exact_release_approval"
    elif release_eligible_ids:
        final_route = (
            "blocked_okx_portability"
            if "blocked_okx_portability" in release_blockers
            else "blocked_okx_data"
        )
    elif data_blocked and candidate_count == 0:
        final_route = "blocked_formal_data"
    else:
        final_route = "completed_zero_qualified_candidates"

    budget_summary = {
        **active_budget.to_dict(),
        "campaignsUsed": campaign_count,
        "candidateTrialsUsed": candidate_count,
        "structuralRevisionsUsed": structural_revision_count,
        "formalCandidatesUsed": formal_candidate_count,
        "fullBacktestsUsed": full_backtests_used,
        "fullBacktestsRemaining": max(
            0, active_budget.maximum_additional_full_backtests - full_backtests_used
        ),
        "demoReleasesUsed": len(releases),
    }
    summary: dict[str, Any] = {
        "schemaVersion": "automatic_strategy_renewal_summary_v1",
        "programId": program_id,
        "parentProgramId": PARENT_PROGRAM_ID,
        "finalRoute": final_route,
        "generatedAt": generated_at,
        "implementationCommit": implementation_commit,
        "baselineMergeCommits": dict(baseline_merge_commits or {}),
        "historicalMutationCount": 0,
        "eligibilityWindowPolicyHash": eligibility_window_policy_hash,
        "benchmarkComparabilityPolicyHash": benchmark_comparability_policy_hash,
        "campaignCount": campaign_count,
        "familyCountByStrategyType": {
            key: len(value) for key, value in sorted(families_by_type.items())
        },
        "candidateCount": candidate_count,
        "prefilterSurvivorCount": prefilter_survivor_count,
        "formalCandidateCount": formal_candidate_count,
        "researchPassCount": research_pass_count,
        "formalPassCount": formal_pass_count,
        "archivedCount": archived_count,
        "structuralRevisionCount": structural_revision_count,
        "formalRunCount": formal_run_count,
        "resultReadCount": result_read_count,
        "lockedOosReadCount": 0,
        "releaseEligibleCandidateIds": release_eligible_ids,
        "releaseCount": len(releases),
        "approvalCount": 0,
        "releases": [
            {
                "releaseId": release["releaseId"],
                "releaseHash": release["releaseHash"],
                "candidateId": release["candidateId"],
                "riskOverlayHash": release["riskOverlayHash"],
                "approved": False,
            }
            for release in releases
        ],
        "approvalRequestHashes": [
            request["approvalRequestHash"] for request in approval_requests
        ],
        "releaseAdmissionBlockers": sorted(set(release_blockers)),
        "demoArm": False,
        "orderCount": 0,
        "budget": budget_summary,
        "liveEnabled": False,
        "tradeApiEnabled": False,
        "withdrawEnabled": False,
    }
    summary["summaryHash"] = stable_hash(summary, prefix="research_renewal_summary")
    write_json_atomic(root / "program_budget.json", budget_summary)
    write_json_atomic(root / "program_state.json", {
        "schemaVersion": "automatic_strategy_renewal_state_v1",
        "programId": program_id,
        "stage": final_route,
        "terminalRoute": final_route if final_route in _TERMINAL_ROUTES else None,
        "nextAllowedStage": final_route,
        "approved": False,
        "demoArm": False,
        "orderCount": 0,
        "generatedAt": generated_at,
    })
    write_json_atomic(summary_path, summary)
    _write_markdown(
        root / "program_summary.md",
        "V28-V32 Research Renewal Program",
        [
            ("Program ID", program_id),
            ("Parent Program", PARENT_PROGRAM_ID),
            ("Final route", final_route),
            ("Campaigns", campaign_count),
            ("Candidates", candidate_count),
            ("Formal pass", formal_pass_count),
            ("Research pass", research_pass_count),
            ("Release eligible", len(release_eligible_ids)),
            ("Releases", len(releases)),
            ("Demo ARM", False),
            ("Orders", 0),
        ],
    )
    ledger.append(
        event_type="program_completed",
        stage=(
            "v32_exact_release_approval"
            if final_route == "blocked_waiting_exact_release_approval"
            else "v31_okx_release_admission"
            if release_eligible_ids
            else "v30_completed"
        ),
        created_at=generated_at,
        payload={"finalRoute": final_route, "summaryHash": summary["summaryHash"]},
    )
    write_json_atomic(paths.artifact_manifest, _manifest(root))
    return summary


__all__ = [
    "PARENT_PROGRAM_ID",
    "ResearchRenewalBudget",
    "build_research_renewal_program_id",
    "refresh_artifact_manifest",
    "run_research_renewal_program",
]
