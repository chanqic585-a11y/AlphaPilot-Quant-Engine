"""Generate the additive V46 provisional Demo sidecar evidence bundle."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from alphapilot.evolution.registry.hashing import stable_hash

from .contracts import (
    build_cooldown_semantics,
    build_portfolio_definition,
    build_provisional_release,
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
    test_summary: Mapping[str, Any],
) -> dict[str, Any]:
    v46 = Path(v46_report_dir).resolve()
    v49 = Path(v49_identity_dir).resolve()
    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)

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
        components.append(
            {
                **dict(sleeve),
                "strategyDefinitionHash": strategy.get("strategyContentHash"),
                "strategyDefinition": strategy,
                "sourceContractHash": contract.get("contractHash"),
                "sourceReleaseHash": contract.get("releaseContentHash"),
                "sourceReleaseMode": contract.get("releaseMode"),
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
    release_id = "provisional_research_demo_v46_" + definition["portfolioDefinitionHash"].split("_")[-1][:24]
    release = build_provisional_release(
        release_id=release_id,
        portfolio_definition=definition,
        risk_overlay=risk,
        universe_audit=universe,
        historical_metrics=dict(summary["bestPolicyMetrics"]),
        cost_stress_metrics=dict(selected_result["stressMetrics"]["plus_0.10R"]),
        replay_parity_percent=replay_parity_percent,
        generated_at=generated_at,
    )

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
    approval = {
        "schemaVersion": "demo_exact_hash_approval_request_v1",
        "releaseId": release["releaseId"],
        "releaseHash": release["releaseHash"],
        "riskOverlayHash": risk["riskOverlayHash"],
        "portfolioComponents": candidate_ids,
        "cooldownSemantics": cooldown,
        "executionInstruments": universe["executionIntersection"],
        "riskLimits": {
            "riskPerTradePercent": risk["riskPerTradePercent"],
            "maximumPortfolioOpenRiskPercent": risk["maximumPortfolioOpenRiskPercent"],
            "maximumConcurrentPositions": risk["maximumConcurrentPositions"],
        },
        "knownLimitations": [
            "V46 remains development_selected_result and is not a Formal Pass.",
            "No clean historical OOS pass exists for this frozen release.",
            "No post-approval closed OKX Demo strategy trade exists yet.",
            "The exact public and authenticated instrument lists were not retained; the runtime eligible intersection was retained.",
            "Live promotion is forbidden and must not be inferred from Demo evidence.",
        ],
        "approvalRequired": True,
        "approved": False,
        "demoArm": False,
        "route": "blocked_waiting_exact_release_approval",
        "requiredUserApproval": (
            "Approve the exact Release Hash and exact Risk Overlay Hash in a later message."
        ),
    }
    approval_md = (
        "# V46 Portfolio Provisional Demo Approval Request\n\n"
        f"- Release ID: `{release['releaseId']}`\n"
        f"- Release Hash: `{release['releaseHash']}`\n"
        f"- Risk Overlay Hash: `{risk['riskOverlayHash']}`\n"
        f"- Components: {', '.join(candidate_ids)}\n"
        "- Cooldown: previous accepted same-pair exit + 14 x 24 elapsed UTC hours; "
        "equality at the boundary is allowed.\n"
        f"- Demo instruments: {', '.join(universe['executionIntersection'])}\n"
        "- Formal pass: false\n- Live eligible: false\n- Approved: false\n- Demo ARM: false\n"
        "- Route: `blocked_waiting_exact_release_approval`\n\n"
        "A later approval must name both exact hashes. This document is not approval.\n"
    )

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
        "demo_approval_request.json": approval,
        "patch_implementation_receipt.json": dict(implementation_receipt),
        "patch_test_summary.json": dict(test_summary),
    }
    for name, payload in payloads.items():
        _write(root / name, payload)
    (root / "cooldown_rejected_signal_ledger.jsonl").write_text("", encoding="utf-8")
    (root / "demo_approval_request.md").write_text(approval_md, encoding="utf-8")
    _write(root / "patch_artifact_manifest.json", _manifest(root, generated_at))
    return {
        "releaseId": release["releaseId"],
        "releaseHash": release["releaseHash"],
        "riskOverlayHash": risk["riskOverlayHash"],
        "route": release["route"],
    }
