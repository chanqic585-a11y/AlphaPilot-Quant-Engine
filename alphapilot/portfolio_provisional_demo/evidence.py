"""Generate the additive V46 provisional Demo sidecar evidence bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from alphapilot.evolution.registry.hashing import stable_hash

from .contracts import (
    build_cooldown_semantics,
    build_execution_identity,
    build_portfolio_definition,
    build_provisional_release,
    build_release_binding_audit,
    build_risk_overlay,
    build_universe_audit,
)


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _component_contracts(root: Path, candidate_ids: list[str]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        try:
            contract = _read(path)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        candidate_id = str(contract.get("strategyCandidateId") or "")
        if candidate_id in candidate_ids:
            current = found.get(candidate_id)
            release_id = str(contract.get("demoReleaseId") or "")
            if current is None or release_id.startswith("demo_release_top100"):
                found[candidate_id] = {**contract, "_sourcePath": path.name}
    missing = sorted(set(candidate_ids) - set(found))
    if missing:
        raise ValueError("component_contracts_missing:" + ",".join(missing))
    return found


def _selected_policy_result(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        if (row.get("policy") or {}).get("policy_id") == "pair_14d_cooldown":
            return row
    raise ValueError("pair_14d_cooldown_result_missing")


def _manifest(root: Path, generated_at: str) -> dict[str, Any]:
    artifacts = []
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.name == "patch_artifact_manifest.json":
            continue
        artifacts.append(
            {"path": path.name, "bytes": path.stat().st_size, "sha256": _sha(path)}
        )
    core = {"generatedAt": generated_at, "artifactCount": len(artifacts), "artifacts": artifacts}
    return {**core, "manifestHash": stable_hash(core, prefix="patch_artifact_manifest")}


def generate_patch_evidence(
    *,
    v46_report_dir: str | Path,
    v49_identity_dir: str | Path,
    component_contract_dir: str | Path,
    output_dir: str | Path,
    research_instruments: Iterable[str],
    public_snapshot_hash: str,
    public_count: int,
    authenticated_hash: str,
    authenticated_count: int,
    authenticated_exact_list_retained: bool,
    runtime_snapshot_hash: str,
    runtime_instruments: Iterable[str],
    v46_evidence_zip_sha256: str,
    v46_evidence_verification: Mapping[str, Any],
    replay_implementation_path: str,
    replay_implementation_sha256: str,
    replay_parity_percent: float,
    replay_parity_audit: Mapping[str, Any],
    generated_at: str,
    implementation_receipt: Mapping[str, Any],
    console_runtime_implementation_sha256: str,
    test_summary: Mapping[str, Any],
) -> dict[str, Any]:
    v46 = Path(v46_report_dir).resolve()
    v49 = Path(v49_identity_dir).resolve()
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    previous_release_path = root / "provisional_release.json"
    previous_release = _read(previous_release_path) if previous_release_path.is_file() else None
    previous_approval_path = root / "demo_approval_request.json"
    previous_approval = (
        _read(previous_approval_path) if previous_approval_path.is_file() else None
    )
    previous_approval_md_path = root / "demo_approval_request.md"
    previous_approval_md = (
        previous_approval_md_path.read_text(encoding="utf-8")
        if previous_approval_md_path.is_file()
        else None
    )

    verification = dict(v46_evidence_verification)
    verified_rows = list(verification.get("verifiedArtifacts") or [])
    if (
        verification.get("status") != "verified"
        or int(verification.get("artifactCount") or 0) < 15
        or not verified_rows
        or any(row.get("verified") is not True for row in verified_rows)
    ):
        raise ValueError("v46_evidence_verification_incomplete")
    if not str(v46_evidence_zip_sha256).strip():
        raise ValueError("v46_evidence_zip_hash_missing")
    if list(implementation_receipt.get("unresolvedImplementationBlockers") or []):
        raise ValueError("unresolved_implementation_blockers")
    if test_summary.get("status") != "passed":
        raise ValueError("patch_tests_not_passed")
    if (
        replay_parity_audit.get("status") != "passed"
        or float(replay_parity_audit.get("parityPercent") or 0) != 100.0
        or float(replay_parity_percent) != 100.0
    ):
        raise ValueError("v46_replay_parity_incomplete")

    candidate = _read(v49 / "v49_portfolio_candidate_spec.json")
    summary = _read(v46 / "campaign_summary.json")
    if summary.get("status") != "development_only":
        raise ValueError("v46_historical_evidence_class_changed")
    checks = dict(summary.get("bestPolicyChecks") or {})
    if not checks or not all(value is True for value in checks.values()):
        raise ValueError("v46_development_selection_checks_incomplete")
    selected_result = _selected_policy_result(_read(v46 / "policy_results.json"))
    candidate_ids = [str(row["candidateId"]) for row in candidate["sleeves"]]
    contracts = _component_contracts(Path(component_contract_dir).resolve(), candidate_ids)

    components = []
    for sleeve in candidate["sleeves"]:
        candidate_id = str(sleeve["candidateId"])
        contract = contracts[candidate_id]
        strategy = dict(contract.get("strategy") or {})
        risk_envelope = dict(contract.get("riskEnvelope") or {})
        components.append(
            {
                **dict(sleeve),
                "strategyDefinitionHash": strategy.get("strategyContentHash"),
                "strategyDefinition": strategy,
                "sourceContractHash": contract.get("contractHash"),
                "sourceReleaseHash": contract.get("releaseContentHash"),
                "sourceReleaseMode": contract.get("releaseMode"),
                "sourceRiskEnvelopeHash": stable_hash(
                    risk_envelope, prefix="source_risk_envelope"
                ),
                "sourcePath": contract.get("_sourcePath"),
            }
        )

    cooldown = build_cooldown_semantics(
        pair_cooldown_days=int(candidate["selectedPolicy"]["pair_cooldown_days"]),
        implementation_path=replay_implementation_path,
        implementation_sha256=replay_implementation_sha256,
    )
    first_risk = dict(contracts[candidate_ids[0]].get("riskEnvelope") or {})
    definition = build_portfolio_definition(
        candidate_id=str(candidate["candidateId"]),
        source_candidate_hash=str(candidate["candidateHash"]),
        source_campaign_hash=str(candidate["sourceCampaignHash"]),
        components=components,
        selected_policy=dict(candidate["selectedPolicy"]),
        cooldown_semantics=cooldown,
        allocation_semantics=str(candidate["allocationSemantics"]),
        cost_model={
            "feeRate": float(first_risk.get("feeRate", 0.0005)),
            "slippageRate": float(first_risk.get("slippageRate", 0.0002)),
            "additionalCostStressR": [0.05, 0.10],
        },
    )
    risk = build_risk_overlay(first_risk)
    universe = build_universe_audit(
        research_instruments=research_instruments,
        public_snapshot_hash=public_snapshot_hash,
        public_count=public_count,
        authenticated_hash=authenticated_hash,
        authenticated_count=authenticated_count,
        authenticated_exact_list_retained=authenticated_exact_list_retained,
        runtime_snapshot_hash=runtime_snapshot_hash,
        runtime_instruments=runtime_instruments,
    )
    source_commits = dict(implementation_receipt.get("sourceCommits") or {})
    execution_identity = build_execution_identity(
        portfolio_definition=definition,
        risk_overlay=risk,
        universe_audit=universe,
        quant_implementation_commit=str(source_commits.get("quant") or ""),
        console_execution_commit=str(source_commits.get("console") or ""),
        quant_runtime_implementation_hash=replay_implementation_sha256,
        console_runtime_implementation_hash=console_runtime_implementation_sha256,
    )
    release_id = "provisional_research_demo_v46_" + definition["portfolioDefinitionHash"].split("_")[-1][:24]
    release = build_provisional_release(
        release_id=release_id,
        portfolio_definition=definition,
        risk_overlay=risk,
        universe_audit=universe,
        historical_metrics=dict(summary["bestPolicyMetrics"]),
        cost_stress_metrics=dict(selected_result["stressMetrics"]["plus_0.10R"]),
        replay_parity_percent=replay_parity_percent,
        execution_identity=execution_identity,
        generated_at=generated_at,
    )
    binding_audit = build_release_binding_audit(
        release=release,
        portfolio_definition=definition,
        risk_overlay=risk,
        universe_audit=universe,
    )
    if binding_audit["status"] != "passed":
        raise ValueError("provisional_release_binding_incomplete")
    previous_hash = str((previous_release or {}).get("releaseHash") or "")
    hash_changed = bool(previous_hash and previous_hash != release["releaseHash"])
    cooldown_wording_audit = {
        "schemaVersion": "cooldown_approval_wording_parity_audit_v1",
        "status": "passed",
        "cooldownScope": cooldown["cooldownScope"],
        "cooldownAnchor": cooldown["cooldownAnchor"],
        "cooldownDurationSeconds": cooldown["cooldownDurationSeconds"],
        "timezone": cooldown["timezone"],
        "boundaryRule": cooldown["boundaryRule"],
        "crossComponentScope": cooldown["crossComponentScope"],
        "implementationSha256": cooldown["implementationSha256"],
        "approvalWordingCorrected": True,
        "previousWording": "same-pair exit",
        "correctedWording": (
            "same canonical instrument across all three components; previous accepted "
            "closed-trade exit timestamp plus 1209600 UTC seconds; equality is allowed"
        ),
        "previousReleaseHash": previous_hash or None,
        "releaseHashChanged": hash_changed,
        "decision": (
            "superseding_release_required"
            if hash_changed
            else "new_release_or_existing_hash_already_complete"
        ),
    }

    component_manifest = {
        "schemaVersion": "v46_portfolio_component_manifest_v1",
        "componentCount": 3,
        "components": components,
        "componentWeights": None,
        "componentWeightSemantics": "no_explicit_weights",
        "portfolioDefinitionHash": definition["portfolioDefinitionHash"],
    }
    policy = {
        "schemaVersion": "provisional_release_policy_v1",
        "releasePurpose": "provisional_research_demo",
        "historicalEvidenceClass": "development_selected_result",
        "freshHistoricalOosRequiredBeforeDemo": False,
        "validationRoute": "forward_only",
        "provisionalAdmissionChecks": {
            "v46EvidenceZipVerified": True,
            "v46EvidenceZipSha256": v46_evidence_zip_sha256,
            "v46ArtifactCountVerified": int(verification["artifactCount"]),
            "v46ReplayParityPercent": float(replay_parity_percent),
            "componentIdentityComplete": True,
            "cooldownSemanticsComplete": True,
            "riskOverlayComplete": True,
            "demoExecutionUniverseNonEmpty": True,
            "unresolvedImplementationBlockerCount": 0,
        },
        "legacyExperimentalOverride": {
            "classification": "legacy_experimental_override",
            "executionEnabled": False,
            "forwardEvidenceEligible": False,
            "livePromotionEligible": False,
        },
        "forwardEvidence": {
            "eligible": "approved_release_closed_okx_demo_strategy_trades_only",
            "excluded": [
                "engineering_smoke",
                "legacy_releases",
                "shadow",
                "local_simulation",
                "open_orders",
                "open_positions",
                "historical_backtest",
                "v46_development_results",
            ],
            "preliminaryReviewClosedTradeCount": 30,
            "seriousReviewClosedTradeCount": 100,
            "automaticLivePromotionAllowed": False,
        },
    }
    hash_audit = {
        "releaseId": release["releaseId"],
        "releaseHash": release["releaseHash"],
        "riskOverlayHash": risk["riskOverlayHash"],
        "portfolioDefinitionHash": definition["portfolioDefinitionHash"],
        "executionIntersectionHash": universe["executionIntersectionHash"],
        "exactApprovalRequired": True,
        "approved": False,
        "demoArm": False,
        "v46EvidenceZipSha256": v46_evidence_zip_sha256,
        "v46ArtifactManifestSha256": verification.get("manifestSha256"),
    }
    payloads = {
        "v46_portfolio_component_manifest.json": component_manifest,
        "v46_portfolio_cooldown_semantics_audit.json": cooldown,
        "v46_portfolio_definition_hash.json": definition,
        "v46_portfolio_replay_parity_audit.json": dict(replay_parity_audit),
        "provisional_release_policy.json": policy,
        "provisional_release.json": release,
        "provisional_release_hash_audit.json": hash_audit,
        "provisional_portfolio_risk_overlay.json": risk,
        "demo_execution_universe_audit.json": universe,
        "cooldown_approval_wording_parity_audit.json": cooldown_wording_audit,
        "provisional_release_binding_audit.json": binding_audit,
        "patch_implementation_receipt.json": dict(implementation_receipt),
        "patch_test_summary.json": dict(test_summary),
    }
    if previous_approval is not None:
        payloads["superseded_demo_approval_request_original.json"] = {
            **dict(previous_approval),
            "superseded": True,
            "supersededReason": "pre_arm_readiness_not_yet_complete",
        }
    if hash_changed:
        payloads["superseded_release_original.json"] = previous_release
        payloads["provisional_release_supersession.json"] = {
            "schemaVersion": "provisional_release_supersession_v1",
            "oldReleaseId": previous_release.get("releaseId"),
            "oldReleaseHash": previous_hash,
            "oldReleaseStatus": "superseded_unapproved",
            "oldApproved": bool(previous_release.get("approved")),
            "oldDemoArm": bool(previous_release.get("demoArm")),
            "supersedingReleaseId": release["releaseId"],
            "supersedingReleaseHash": release["releaseHash"],
            "reason": "execution_identity_and_explicit_cooldown_semantics_were_not_fully_bound",
            "generatedAt": generated_at,
        }
    for name, payload in payloads.items():
        _write(root / name, payload)
    (root / "cooldown_rejected_signal_ledger.jsonl").write_text("", encoding="utf-8")
    if previous_approval_md is not None:
        (root / "superseded_demo_approval_request_original.md").write_text(
            previous_approval_md, encoding="utf-8"
        )
    previous_approval_path.unlink(missing_ok=True)
    previous_approval_md_path.unlink(missing_ok=True)
    _write(root / "patch_artifact_manifest.json", _manifest(root, generated_at))
    return {
        "releaseId": release["releaseId"],
        "releaseHash": release["releaseHash"],
        "riskOverlayHash": risk["riskOverlayHash"],
        "route": release["route"],
    }
