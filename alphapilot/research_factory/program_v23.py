"""V23 immutable Demo Release generation and human-approval boundary."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.research_factory.artifact_paths import ProgramArtifactPaths
from alphapilot.research_factory.program_ledger import ProgramLedger
from alphapilot.research_factory.program_state import ProgramStateStore
from alphapilot.research_factory.program_v19 import _artifact_manifest


_ELIGIBLE_STATUS = {
    "formal_pass": ("standard_demo", "strategy_forward_validation", "demo_strategy_validation"),
    "research_pass_no_clean_holdout": (
        "research_forward",
        "research_forward_validation",
        "demo_research_forward",
    ),
    "research_pass_funding_unavailable": (
        "research_forward",
        "research_forward_validation",
        "demo_research_forward",
    ),
}

_SOURCE_HASH_FIELDS = (
    "strategyDefinitionHash",
    "exitPolicyHash",
    "dataProfileHash",
    "dataManifestHash",
    "preregistrationHash",
    "costModelHash",
    "capitalPolicyHash",
    "benchmarkHash",
    "formalGateHash",
    "backtestReportHash",
)


def _ranking_key(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    status = str(candidate.get("status") or "")
    evidence_priority = 0 if status == "formal_pass" else 1
    return (
        evidence_priority,
        -float(candidate.get("rankingScore") or 0.0),
        -float(candidate.get("stress1_5xProfitFactor") or 0.0),
        -float(candidate.get("averageNetR") or 0.0),
        -int(candidate.get("positiveFoldCount") or 0),
        float(candidate.get("maximumDrawdownPct") or 0.0),
        -float(candidate.get("benchmarkIncrement") or 0.0),
        float(candidate.get("concentrationPct") or 100.0),
        -int(candidate.get("sampleSize") or 0),
        -float(candidate.get("evidenceCompletenessPct") or 0.0),
        str(candidate.get("candidateId") or ""),
    )


def _risk_overlay(release_class: str) -> dict[str, Any]:
    if release_class == "research_forward":
        overlay = {
            "schemaVersion": "automatic_v23_demo_risk_overlay_v1",
            "overlayClass": "research_forward_strict",
            "maximumConcurrentPositions": 1,
            "maximumOpenRiskPctEquity": 0.10,
            "addingAllowed": False,
            "averagingAllowed": False,
            "martingaleAllowed": False,
            "retryPolicy": "bounded",
            "exitPolicyMode": "exact_frozen",
            "mayWidenFrozenRisk": False,
        }
    else:
        overlay = {
            "schemaVersion": "automatic_v23_demo_risk_overlay_v1",
            "overlayClass": "standard_console_ceiling",
            "maximumConcurrentPositions": None,
            "maximumOpenRiskPctEquity": None,
            "addingAllowed": False,
            "averagingAllowed": False,
            "martingaleAllowed": False,
            "retryPolicy": "bounded",
            "exitPolicyMode": "exact_frozen",
            "mayWidenFrozenRisk": False,
        }
    overlay["riskOverlayHash"] = stable_hash(overlay, prefix="automatic_demo_risk_overlay")
    return overlay


def _build_release(
    *,
    campaign_id: str,
    candidate: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    status = str(candidate["status"])
    release_class, purpose, evidence_class = _ELIGIBLE_STATUS[status]
    overlay = _risk_overlay(release_class)
    identity = {
        "campaignId": campaign_id,
        "candidateId": str(candidate["candidateId"]),
        "releaseClass": release_class,
        "evidenceClass": evidence_class,
    }
    release_id = f"automatic_demo_release_{stable_hash(identity)[:16]}"
    release: dict[str, Any] = {
        "schemaVersion": "automatic_v23_immutable_demo_release_v1",
        "releaseId": release_id,
        "campaignId": campaign_id,
        "candidateId": str(candidate["candidateId"]),
        "strategyId": str(candidate.get("strategyId") or candidate["candidateId"]),
        "familyId": str(candidate.get("familyId") or "unspecified"),
        "formalStatus": status,
        "formalPass": status == "formal_pass",
        "releaseClass": release_class,
        "releasePurpose": purpose,
        "evidenceClass": evidence_class,
        "strategyQualification": status == "formal_pass",
        "forwardReviewEligible": release_class == "research_forward",
        "livePromotionEligible": False,
        "approvalRequired": True,
        "approved": False,
        "environment": "demo",
        "demoArm": False,
        "orderCount": 0,
        "riskOverlay": {key: value for key, value in overlay.items() if key != "riskOverlayHash"},
        "riskOverlayHash": overlay["riskOverlayHash"],
        "createdAt": created_at,
    }
    for field in _SOURCE_HASH_FIELDS:
        release[field] = candidate.get(field)
    release["releaseHash"] = stable_hash(release, prefix="automatic_demo_release")
    return release


def build_release_plan(
    *,
    campaign_id: str,
    candidate_results: Sequence[Mapping[str, Any]],
    maximum_release_count: int,
    created_at: str = "1970-01-01T00:00:00Z",
) -> dict[str, Any]:
    """Build a deterministic plan without mutating approval or runtime state."""

    if not campaign_id.strip():
        raise ValueError("campaign_id_required")
    if maximum_release_count < 0 or maximum_release_count > 3:
        raise ValueError("maximum_release_count_must_be_between_0_and_3")
    eligible = [
        dict(candidate)
        for candidate in candidate_results
        if bool(candidate.get("releaseEligible"))
        and str(candidate.get("status") or "") in _ELIGIBLE_STATUS
    ]
    eligible.sort(key=_ranking_key)
    selected = eligible[:maximum_release_count]
    releases = [
        _build_release(campaign_id=campaign_id, candidate=row, created_at=created_at)
        for row in selected
    ]
    release_hashes = [str(row["releaseHash"]) for row in releases]
    zero_release = not releases
    plan = {
        "schemaVersion": "automatic_v23_release_plan_v1",
        "campaignId": campaign_id,
        "maximumReleaseCount": maximum_release_count,
        "eligibleCandidateCount": len(eligible),
        "releaseCount": len(releases),
        "releaseHashes": release_hashes,
        "releases": releases,
        "approvalRequired": not zero_release,
        "automaticApprovalAllowed": False,
        "demoArm": False,
        "orderCount": 0,
        "terminalRoute": "completed_zero_qualified_candidates" if zero_release else None,
    }
    plan["releasePlanHash"] = stable_hash(plan, prefix="automatic_v23_release_plan")
    return plan


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected_json_object:{path}")
    return payload


def _write_ranking_csv(path: Path, candidate_results: Sequence[Mapping[str, Any]]) -> None:
    rows = sorted((dict(row) for row in candidate_results), key=_ranking_key)
    columns = (
        "candidateId",
        "status",
        "releaseEligible",
        "rankingScore",
        "evidenceClass",
        "releaseSelected",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_v23_release_generation(
    *,
    reports_root: Path,
    program_id: str,
    generated_at: str,
    maximum_release_count: int = 3,
) -> dict[str, Any]:
    """Generate immutable eligible releases, or freeze the audited zero route."""

    paths = ProgramArtifactPaths(Path(reports_root), program_id)
    state_store = ProgramStateStore(paths)
    state = state_store.load()
    if state.stage == "release_ready":
        checkpoint = state_store.load_checkpoint("v23")
        return {**checkpoint["payload"], "resumed": True}
    if state.stage != "formal_validation_completed":
        raise ValueError(f"v23_stage_not_allowed:{state.stage}")
    campaign_id = str(state.active_campaign_id or "")
    v22 = state_store.load_checkpoint("v22")["payload"]
    candidate_root = Path(str(v22["artifactRoot"]))
    route = _read_json(candidate_root / "formal_route.json")
    candidate_result = {
        "candidateId": str(route["candidateId"]),
        "status": str(route["status"]),
        "releaseEligible": bool(route.get("releaseEligible")),
        "rankingScore": 0.0,
        "evidenceCompletenessPct": 100.0,
        "backtestReportHash": _read_json(candidate_root / "artifact_manifest.json").get(
            "manifestHash"
        ),
    }
    plan = build_release_plan(
        campaign_id=campaign_id,
        candidate_results=[candidate_result],
        maximum_release_count=maximum_release_count,
        created_at=generated_at,
    )
    release_root = paths.program_root / "candidate_releases"
    release_root.mkdir(parents=True, exist_ok=True)
    for release in plan["releases"]:
        missing_hashes = [field for field in _SOURCE_HASH_FIELDS if not release.get(field)]
        if missing_hashes:
            raise ValueError("release_source_hash_missing:" + ",".join(missing_hashes))
        write_json_atomic(release_root / f"{release['releaseId']}.json", release)

    selected_ids = {str(row["candidateId"]) for row in plan["releases"]}
    ranking_rows = [
        {
            **candidate_result,
            "evidenceClass": (
                _ELIGIBLE_STATUS[str(candidate_result["status"])][2]
                if str(candidate_result["status"]) in _ELIGIBLE_STATUS
                else "ineligible"
            ),
            "releaseSelected": str(candidate_result["candidateId"]) in selected_ids,
        }
    ]
    _write_ranking_csv(paths.program_root / "eligible_candidate_ranking.csv", ranking_rows)
    write_json_atomic(paths.program_root / "release_inventory.json", plan)
    write_json_atomic(
        paths.program_root / "approval_requirements.json",
        {
            "schemaVersion": "automatic_v23_approval_requirements_v1",
            "approvalRequired": plan["approvalRequired"],
            "automaticApprovalAllowed": False,
            "requiredApprovalType": "exact_release_hash" if plan["approvalRequired"] else None,
            "releaseHashes": plan["releaseHashes"],
        },
    )
    write_json_atomic(
        paths.program_root / "zero_release_route.json",
        {
            "schemaVersion": "automatic_v23_zero_release_route_v1",
            "applies": plan["releaseCount"] == 0,
            "terminalRoute": plan["terminalRoute"],
            "importCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
    )

    state = state.transition(
        stage="release_ready",
        updated_at=generated_at,
        stage_attempt=state.stage_attempt + 1,
        previous_checkpoint="v22",
        next_allowed_stage="demo_waiting_approval",
        terminal_route=plan["terminalRoute"],
        human_gate_status="not_required" if plan["releaseCount"] == 0 else "waiting_exact_hash",
    )
    state_store.save(state)
    checkpoint_payload = {
        "programId": program_id,
        "campaignId": campaign_id,
        "status": "completed",
        "releaseCount": plan["releaseCount"],
        "releaseHashes": plan["releaseHashes"],
        "approvalRequired": plan["approvalRequired"],
        "terminalRoute": plan["terminalRoute"],
        "demoArm": False,
        "orderCount": 0,
        "artifactRoot": paths.program_root.as_posix(),
    }
    state_store.write_checkpoint(stage="v23", created_at=generated_at, payload=checkpoint_payload)
    ProgramLedger(paths.ledger).append(
        event_type="v23_release_generation_completed",
        stage=state.stage,
        created_at=generated_at,
        payload=checkpoint_payload,
    )
    write_json_atomic(paths.artifact_manifest, _artifact_manifest(paths.program_root))
    return checkpoint_payload


__all__ = ["build_release_plan", "run_v23_release_generation"]
