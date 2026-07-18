"""Prepare deterministic V18 contracts without opening formal result data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.formal_validation.capital_policy_conformance import (
    audit_capital_policy_v2,
)
from alphapilot.formal_validation.v18_contracts import (
    build_v18_preregistration,
    write_v18_preregistration,
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _reference_payload(source_root: Path, reference: str) -> dict[str, Any]:
    path = source_root / reference
    return {
        "path": reference.replace("\\", "/"),
        "existsAtPreparation": path.is_file(),
        "sha256": sha256_file(path) if path.is_file() else None,
        "contentReadForResults": False,
    }


def _remote_freeze_status(
    *,
    remote_code_commit: str | None,
    remote_preregistration_commit: str | None,
    remote_tag: str | None,
) -> str:
    return (
        "published"
        if remote_code_commit and remote_preregistration_commit and remote_tag
        else "not_published"
    )


def prepare_v18_pre_result_artifacts(
    *,
    source_repo_root: Path,
    output_repo_root: Path,
    v17_provenance_reference: str,
    remote_code_commit: str | None,
    remote_preregistration_commit: str | None,
    remote_tag: str | None,
) -> dict[str, Any]:
    """Freeze V18 pre-result evidence and stop at the remote publication gate."""

    source_root = Path(source_repo_root).resolve()
    output_root = Path(output_repo_root).resolve()
    preregistration = build_v18_preregistration(
        source_root,
        implementation_commit=remote_code_commit,
    )
    preregistration_path = write_v18_preregistration(preregistration, output_root)
    campaign_id = str(preregistration["campaignId"])
    campaign_root = output_root / "reports" / "formal_validation" / campaign_id
    campaign_root.mkdir(parents=True, exist_ok=True)
    policy = preregistration["capitalCompetitionPolicy"]
    remote_freeze = _remote_freeze_status(
        remote_code_commit=remote_code_commit,
        remote_preregistration_commit=remote_preregistration_commit,
        remote_tag=remote_tag,
    )

    correction_manifest: dict[str, Any] = {
        "schemaVersion": "s01_v18_capital_policy_correction_manifest_v1",
        "campaignId": campaign_id,
        "correctionOfCampaignId": "advisory_r_v17",
        "correctionReason": "capital_policy_execution_contract_incomplete",
        "strategyParameterChanges": 0,
        "BearDefinitionChanges": 0,
        "exitPolicyChanges": 0,
        "splitPolicyChanges": 0,
        "universeChanges": 0,
        "costChanges": 0,
        "GateChanges": 0,
        "formalPortfolioPolicyDefinitionChanges": 1,
        "resultDataAccessed": False,
        "lockedOosAccessCount": 0,
    }
    correction_manifest["manifestHash"] = stable_hash(
        correction_manifest, prefix="s01_v18_capital_policy_correction_manifest"
    )

    semantics_audit: dict[str, Any] = {
        "schemaVersion": "s01_v18_capacity_data_semantics_audit_v1",
        "campaignId": campaign_id,
        "status": "passed_contract_only",
        "sourcePriority": policy["capacityModel"]["sourcePriority"],
        "derivativesVolumeRequirement": (
            "contract volume requires verified contract value and multiplier semantics"
        ),
        "lookbackCompletedUtcDays": 30,
        "minimumCompletedUtcDays": 24,
        "pointInTimePolicy": "strictly_prior_completed_utc_days_only",
        "missingDataPolicy": "reject_without_fallback",
        "resultDataAccessed": False,
        "lookaheadReadCount": 0,
        "capacityModelHash": preregistration["capacityModelHash"],
    }
    semantics_audit["auditHash"] = stable_hash(
        semantics_audit, prefix="s01_v18_capacity_data_semantics_audit"
    )

    conformance_issues = audit_capital_policy_v2(policy)
    conformance: dict[str, Any] = {
        "schemaVersion": "s01_v18_capital_policy_conformance_v1",
        "campaignId": campaign_id,
        "status": "passed" if not conformance_issues else "failed",
        "issues": conformance_issues,
        "fallbackFieldCount": 0,
        "unusedResultAffectingFieldCount": 0,
        "canonicalAcceptanceSequence": policy["acceptanceSequence"],
        "formalPortfolioPolicyV2Hash": preregistration[
            "formalPortfolioPolicyV2Hash"
        ],
        "resultExecutionAllowed": False,
        "resultDataAccessed": False,
    }
    conformance["auditHash"] = stable_hash(
        conformance, prefix="s01_v18_capital_policy_conformance"
    )

    prereg_reference: dict[str, Any] = {
        "schemaVersion": "s01_v18_formal_preregistration_reference_v1",
        "campaignId": campaign_id,
        "path": preregistration_path.relative_to(output_root).as_posix(),
        "preregistrationHash": preregistration["preregistrationHash"],
        "remoteCodeCommit": remote_code_commit,
        "remotePreregistrationCommit": remote_preregistration_commit,
        "remoteTag": remote_tag,
        "remoteFreezeStatus": remote_freeze,
        "formalRunAllowed": remote_freeze == "published",
    }

    future_oos_reference: dict[str, Any] = {
        "schemaVersion": "s01_v18_future_locked_oos_identity_reference_v1",
        "campaignId": campaign_id,
        "status": (
            "ready_for_identity_creation"
            if remote_freeze == "published"
            else "pending_remote_freeze"
        ),
        "plannedPath": "research/locked_oos/s01_v18_future_locked_oos_identity.json",
        "plannedAccessLedgerPath": (
            "research/locked_oos/s01_v18_future_locked_oos_access_ledger.jsonl"
        ),
        "startRule": (
            "first_4h_boundary_strictly_after_code_and_preregistration_remote_freeze"
        ),
        "timeframe": "4h",
        "coreUniverseHash": preregistration["coreUniverseHash"],
        "strategyDefinitionHash": preregistration["strategyDefinitionHash"],
        "formalPortfolioPolicyV2Hash": preregistration[
            "formalPortfolioPolicyV2Hash"
        ],
        "preregistrationHash": preregistration["preregistrationHash"],
        "contentRead": False,
        "accessCount": 0,
        "metadataOnly": True,
        "identityCreated": False,
    }

    route: dict[str, Any] = {
        "schemaVersion": "s01_v18_pre_result_route_v1",
        "campaignId": campaign_id,
        "route": (
            "ready_for_formal_research_run"
            if remote_freeze == "published"
            else "blocked_remote_freeze"
        ),
        "remoteFreezeStatus": remote_freeze,
        "formalRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "stopImmediately": remote_freeze != "published",
    }

    summary: dict[str, Any] = {
        "schemaVersion": "s01_v18_pre_result_campaign_summary_v1",
        "campaignId": campaign_id,
        "status": "pre_result_frozen",
        "route": route["route"],
        "preregistrationHash": preregistration["preregistrationHash"],
        "strategyDefinitionHash": preregistration["strategyDefinitionHash"],
        "exitPolicyHash": preregistration["exitPolicyHash"],
        "formalPortfolioPolicyV2Hash": preregistration[
            "formalPortfolioPolicyV2Hash"
        ],
        "formalRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "knownIssues": [
            "remote code, preregistration, and tag are not yet frozen together"
        ]
        if remote_freeze != "published"
        else [],
    }

    artifacts: dict[str, Mapping[str, Any]] = {
        "correction_manifest.json": correction_manifest,
        "v17_closeout_provenance_reference.json": _reference_payload(
            source_root, v17_provenance_reference
        ),
        "capacity_data_semantics_audit.json": semantics_audit,
        "capacity_model_contract.json": policy["capacityModel"],
        "correlation_cluster_policy_contract.json": policy[
            "correlationClusterPolicy"
        ],
        "portfolio_beta_policy_contract.json": policy["portfolioBetaPolicy"],
        "signal_ranking_policy_contract.json": policy["rankingPolicy"],
        "formal_portfolio_policy_v2.json": policy,
        "capital_policy_conformance.json": conformance,
        "formal_preregistration_reference.json": prereg_reference,
        "future_locked_oos_identity_reference.json": future_oos_reference,
        "route_decision.json": route,
        "campaign_summary.json": summary,
    }
    for filename, payload in artifacts.items():
        write_json_atomic(campaign_root / filename, dict(payload))

    _write_markdown(
        campaign_root / "campaign_summary.md",
        [
            "# V18 S01 Capital Policy Correction",
            "",
            f"- Campaign: `{campaign_id}`",
            f"- Route: `{route['route']}`",
            f"- Formal run count: `{summary['formalRunCount']}`",
            f"- Locked OOS access count: `{summary['lockedOosAccessCount']}`",
            f"- Release / Demo ARM / orders: `{summary['releaseCount']} / {summary['demoArm']} / {summary['orderCount']}`",
            "- Scope: executable capital policy definitions only; no strategy, exit, split, universe, cost, or gate change.",
            "- Result data has not been opened.",
        ],
    )

    manifest_files = sorted(
        path for path in campaign_root.iterdir() if path.name != "artifact_manifest.json"
    )
    manifest: dict[str, Any] = {
        "schemaVersion": "s01_v18_pre_result_artifact_manifest_v1",
        "campaignId": campaign_id,
        "artifacts": [
            {
                "path": path.name,
                "sha256": sha256_file(path),
                "byteCount": path.stat().st_size,
            }
            for path in manifest_files
        ],
        "formalResultArtifactCount": 0,
        "lockedOosContentArtifactCount": 0,
        "releaseArtifactCount": 0,
        "orderArtifactCount": 0,
    }
    manifest["manifestHash"] = stable_hash(
        manifest, prefix="s01_v18_pre_result_artifact_manifest"
    )
    write_json_atomic(campaign_root / "artifact_manifest.json", manifest)

    return {
        "campaignId": campaign_id,
        "campaignRoot": campaign_root,
        "preregistrationPath": preregistration_path,
        "route": route["route"],
    }
