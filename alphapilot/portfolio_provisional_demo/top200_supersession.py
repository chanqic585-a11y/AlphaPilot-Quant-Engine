"""Additive TOP200 supersession for an unapproved provisional Demo release."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.portfolio_provisional_demo.contracts import (
    validate_provisional_release,
)
from alphapilot.portfolio_provisional_demo.readiness import (
    build_exact_release_approval_request,
)


def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name}_missing")
    return text


def _validate_inputs(
    *,
    old_release: Mapping[str, Any],
    policy: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    risk_overlay: Mapping[str, Any],
    engineering_smoke_audit: Mapping[str, Any],
) -> list[str]:
    validate_provisional_release(old_release)
    if old_release.get("approved") is not False or old_release.get("demoArm") is not False:
        raise PermissionError("only_unapproved_unarmed_release_can_be_superseded")
    if policy.get("schemaVersion") != "okx_demo_top200_universe_policy_v1":
        raise ValueError("unsupported_top200_policy")
    if policy.get("resultBasedSelectionAllowed") is not False:
        raise PermissionError("result_based_top200_selection_forbidden")
    if snapshot.get("schemaVersion") != "okx_demo_top200_universe_snapshot_v1":
        raise ValueError("unsupported_top200_snapshot")
    if snapshot.get("status") != "ready":
        raise ValueError("top200_snapshot_not_ready")
    if (
        snapshot.get("policyId") != policy.get("policyId")
        or snapshot.get("policyHash") != policy.get("policyHash")
    ):
        raise ValueError("top200_snapshot_policy_mismatch")
    instruments = [
        str(value).strip().upper()
        for value in snapshot.get("instrumentIds") or []
        if str(value).strip()
    ]
    if not instruments or len(instruments) != len(set(instruments)):
        raise ValueError("top200_snapshot_instruments_invalid")
    if int(snapshot.get("actualInstrumentCount") or 0) != len(instruments):
        raise ValueError("top200_snapshot_count_mismatch")
    maximum = int(snapshot.get("maximumInstrumentCount") or 0)
    if maximum < len(instruments) or maximum > 200:
        raise ValueError("top200_snapshot_limit_invalid")
    risk_hash = _required_text(risk_overlay.get("riskOverlayHash"), "risk_overlay_hash")
    if old_release.get("riskOverlayHash") != risk_hash:
        raise ValueError("risk_overlay_hash_changed")
    if engineering_smoke_audit.get("engineeringSmokeReady") is not True:
        raise ValueError("compatible_engineering_smoke_required")
    return instruments


def build_top200_supersession_bundle(
    *,
    old_release: Mapping[str, Any],
    policy: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    risk_overlay: Mapping[str, Any],
    engineering_smoke_audit: Mapping[str, Any],
    engineering_smoke_contract: Mapping[str, Any],
    quant_implementation_commit: str,
    console_execution_commit: str,
    quant_runtime_implementation_hash: str,
    console_runtime_implementation_hash: str,
    generated_at: str,
) -> dict[str, dict[str, Any]]:
    """Freeze a new exact identity without mutating the five-instrument release."""

    instruments = _validate_inputs(
        old_release=old_release,
        policy=policy,
        snapshot=snapshot,
        risk_overlay=risk_overlay,
        engineering_smoke_audit=engineering_smoke_audit,
    )
    old_hash = _required_text(old_release.get("releaseHash"), "old_release_hash")
    old_id = _required_text(old_release.get("releaseId"), "old_release_id")
    policy_id = _required_text(policy.get("policyId"), "top200_policy_id")
    policy_hash = _required_text(policy.get("policyHash"), "top200_policy_hash")
    snapshot_hash = _required_text(snapshot.get("snapshotHash"), "top200_snapshot_hash")
    intersection_hash = stable_hash(instruments, prefix="demo_execution_intersection")

    old_identity = deepcopy(dict(old_release.get("executionIdentity") or {}))
    old_identity.pop("executionIdentityHash", None)
    identity_core = {
        **old_identity,
        "quantImplementationCommit": _required_text(
            quant_implementation_commit, "quant_implementation_commit"
        ),
        "consoleExecutionCommit": _required_text(
            console_execution_commit, "console_execution_commit"
        ),
        "quantRuntimeImplementationHash": _required_text(
            quant_runtime_implementation_hash, "quant_runtime_implementation_hash"
        ),
        "consoleRuntimeImplementationHash": _required_text(
            console_runtime_implementation_hash, "console_runtime_implementation_hash"
        ),
        "dynamicUniversePolicyId": policy_id,
        "dynamicUniversePolicyHash": policy_hash,
        "dynamicUniverseSnapshotHash": snapshot_hash,
        "dynamicUniverseSnapshotUtcDate": _required_text(
            snapshot.get("utcDate"), "top200_snapshot_utc_date"
        ),
        "dynamicUniverseActualInstrumentCount": len(instruments),
        "publicUniverseSnapshotHash": snapshot_hash,
        "authenticatedDemoUniverseHash": snapshot_hash,
        "confirmedRuntimeUniverseHash": snapshot_hash,
        "executionIntersectionHash": intersection_hash,
    }
    identity = {
        **identity_core,
        "executionIdentityHash": stable_hash(
            identity_core, prefix="provisional_demo_execution_identity"
        ),
    }
    release_identity = {
        "supersedesReleaseId": old_id,
        "supersedesReleaseHash": old_hash,
        "portfolioDefinitionHash": old_release.get("portfolioDefinitionHash"),
        "riskOverlayHash": old_release.get("riskOverlayHash"),
        "dynamicUniversePolicyHash": policy_hash,
        "dynamicUniverseSnapshotHash": snapshot_hash,
        "executionIdentityHash": identity["executionIdentityHash"],
    }
    release_id = (
        "provisional_research_demo_top200_"
        + stable_hash(release_identity, prefix="release_identity").rsplit("_", 1)[-1][:24]
    )
    release_core = deepcopy(dict(old_release))
    release_core.pop("releaseHash", None)
    release_core.update(
        {
            "releaseId": release_id,
            "supersedesReleaseId": old_id,
            "supersedesReleaseHash": old_hash,
            "dynamicUniversePolicyId": policy_id,
            "dynamicUniversePolicyHash": policy_hash,
            "dynamicUniverseSnapshotHash": snapshot_hash,
            "dynamicUniverseSnapshotUtcDate": snapshot.get("utcDate"),
            "maximumInstrumentCount": int(snapshot.get("maximumInstrumentCount") or 200),
            "actualInstrumentCount": len(instruments),
            "executionIntersectionHash": intersection_hash,
            "executionInstruments": instruments,
            "executionIdentity": identity,
            "executionIdentityHash": identity["executionIdentityHash"],
            "historicalEvidenceClass": "development_selected_result",
            "formalPass": False,
            "cleanHistoricalOosPass": False,
            "livePromotionEligible": False,
            "automaticLivePromotionAllowed": False,
            "approvalRequired": True,
            "approved": False,
            "demoArm": False,
            "route": "blocked_waiting_exact_release_approval",
            "generatedAt": generated_at,
        }
    )
    release = {
        **release_core,
        "releaseHash": stable_hash(release_core, prefix="provisional_demo_release"),
    }
    validate_provisional_release(release)

    approval = build_exact_release_approval_request(
        release=release,
        readiness={
            "approvalReady": True,
            "route": "blocked_waiting_exact_release_approval",
        },
        smoke_audit=engineering_smoke_audit,
        smoke_contract=engineering_smoke_contract,
        generated_at=generated_at,
    )
    overlay = {
        "schemaVersion": "provisional_release_supersession_overlay_v1",
        "generatedAt": generated_at,
        "oldReleaseId": old_id,
        "oldReleaseHash": old_hash,
        "oldReleaseStatus": "superseded_unapproved",
        "oldApproved": False,
        "oldDemoArm": False,
        "supersedingReleaseId": release_id,
        "supersedingReleaseHash": release["releaseHash"],
        "reason": "dynamic_top200_execution_identity_supersession",
        "historicalArtifactMutation": False,
    }
    hash_audit = {
        "schemaVersion": "top200_superseding_release_hash_audit_v1",
        "generatedAt": generated_at,
        "releaseId": release_id,
        "releaseHash": release["releaseHash"],
        "riskOverlayHash": release["riskOverlayHash"],
        "dynamicUniversePolicyId": policy_id,
        "dynamicUniversePolicyHash": policy_hash,
        "dynamicUniverseSnapshotHash": snapshot_hash,
        "actualInstrumentCount": len(instruments),
        "executionIntersectionHash": intersection_hash,
        "engineeringSmokeEvidenceHash": engineering_smoke_audit.get("evidenceHash"),
        "oldReleaseUnchanged": True,
        "approvalRequired": True,
        "approved": False,
        "demoArm": False,
        "strategyOrderCount": 0,
        "live": False,
        "withdraw": False,
        "status": "blocked_waiting_exact_release_approval",
    }
    return {
        "supersedingRelease": release,
        "supersedingReleaseHashAudit": hash_audit,
        "approvalRequest": approval,
        "oldReleaseSupersessionOverlay": overlay,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> str:
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_top200_supersession_bundle(
    output_dir: Path | str,
    bundle: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Write only additive TOP200 files and return their deterministic manifest."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "superseding_provisional_release.json": bundle["supersedingRelease"],
        "superseding_release_hash_audit.json": bundle[
            "supersedingReleaseHashAudit"
        ],
        "superseding_demo_approval_request.json": bundle["approvalRequest"],
        "old_release_supersession_overlay.json": bundle[
            "oldReleaseSupersessionOverlay"
        ],
    }
    entries = [
        {"path": name, "sha256": _write_json(root / name, payload)}
        for name, payload in artifacts.items()
    ]
    manifest = {
        "schemaVersion": "top200_supersession_artifact_manifest_v1",
        "artifactCount": len(entries) + 1,
        "artifacts": entries,
        "manifestIncludedInArtifactCount": True,
        "releaseHash": bundle["supersedingRelease"].get("releaseHash"),
        "riskOverlayHash": bundle["supersedingRelease"].get("riskOverlayHash"),
        "approved": False,
        "demoArm": False,
        "strategyOrderCount": 0,
        "live": False,
        "withdraw": False,
    }
    _write_json(root / "top200_supersession_artifact_manifest.json", manifest)
    return manifest
