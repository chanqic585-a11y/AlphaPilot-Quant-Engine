"""Verify V46 evidence and freeze the V49 portfolio identity before result reads."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from alphapilot.evolution.registry.hashing import stable_hash


V49_CANDIDATE_ID = "v49_three_mechanism_same_symbol_14d_cooldown_portfolio_v1"
SELECTED_POLICY_ID = "pair_14d_cooldown"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_v46_manifest(v46_root: Path) -> dict[str, Any]:
    manifest = _read_json(v46_root / "artifact_manifest.json")
    failures: list[dict[str, str]] = []
    verified: list[dict[str, Any]] = []
    for row in manifest.get("artifacts", []):
        path = v46_root / str(row["path"])
        actual = _sha256(path) if path.is_file() else None
        expected = str(row.get("sha256") or "")
        verified.append(
            {
                "path": str(row["path"]),
                "expectedSha256": expected,
                "actualSha256": actual,
                "verified": actual == expected,
            }
        )
        if actual != expected:
            failures.append({"path": str(row["path"]), "reason": "sha256_mismatch"})
    if failures:
        raise ValueError("v46_artifact_manifest_verification_failed")
    return {
        "artifactCount": len(verified),
        "manifestSha256": _sha256(v46_root / "artifact_manifest.json"),
        "status": "verified",
        "verifiedArtifacts": verified,
    }

def _publish_receipt(payload: Mapping[str, Any], generated_at: str) -> dict[str, Any]:
    commit = str(payload.get("commit") or "")
    remote_commit = str(payload.get("remoteCommit") or "")
    pushed = bool(payload.get("pushed"))
    if not commit or not pushed or commit != remote_commit:
        raise ValueError("v46_publish_receipt_not_verified")
    return {
        **dict(payload),
        "commitMatchesRemote": True,
        "pushed": True,
        "verifiedAt": generated_at,
    }


def _selection_evidence(
    policy_results: list[dict[str, Any]],
    selected_policy_id: str,
    generated_at: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    trials = []
    for index, row in enumerate(policy_results, start=1):
        policy = dict(row.get("policy") or {})
        trials.append(
            {
                "observedOrder": index,
                "policyId": policy.get("policy_id"),
                "policyHash": policy.get("policy_hash"),
                "metricsReadDuringDevelopment": True,
                "selected": policy.get("policy_id") == selected_policy_id,
            }
        )
    ledger = {
        "generatedAt": generated_at,
        "observedPolicyTrialCount": len(trials),
        "policyTrials": trials,
        "selectedPolicyId": selected_policy_id,
        "upstreamStrategySelectionTrialCount": "unavailable",
    }
    audit = {
        "formalStatisticalPassAllowed": False,
        "generatedAt": generated_at,
        "policySelectionResultReadBeforeChoice": True,
        "policyTrialCount": len(trials),
        "provisionalResearchDemoAllowed": True,
        "selectionTrialCount": "unavailable",
        "status": "selection_bias_disclosed",
        "upstreamStrategySelectionHistoryAvailable": False,
        "permittedUse": ["fresh_preregistered_forward_validation", "research_only"],
        "forbiddenLabels": ["oos_pass", "formal_pass", "forward_pass", "live_candidate"],
    }
    return ledger, audit


def _component_manifest(preregistration: Mapping[str, Any]) -> dict[str, Any]:
    contract = preregistration.get("contract") or {}
    ledgers = {
        str(row.get("candidateId")): row
        for row in preregistration.get("ledgers", [])
        if isinstance(row, dict)
    }
    components = []
    for sleeve in contract.get("sleeves", []):
        candidate_id = str(sleeve.get("candidate_id") or "")
        ledger = ledgers.get(candidate_id, {})
        components.append(
            {
                "candidateId": candidate_id,
                "direction": sleeve.get("direction"),
                "family": sleeve.get("family"),
                "ledgerSha256": ledger.get("sha256"),
                "sleeveHash": sleeve.get("sleeve_hash"),
                "timeframe": sleeve.get("timeframe"),
            }
        )
    return {
        "componentCount": len(components),
        "components": components,
        "sourceCampaignHash": preregistration.get("campaignHash"),
    }


def _selected_policy(policy_results: list[dict[str, Any]]) -> dict[str, Any]:
    for row in policy_results:
        policy = dict(row.get("policy") or {})
        if policy.get("policy_id") == SELECTED_POLICY_ID:
            return policy
    raise ValueError("selected_v46_policy_missing")


def _artifact_manifest(root: Path, generated_at: str) -> dict[str, Any]:
    rows = []
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        rows.append(
            {
                "bytes": path.stat().st_size,
                "path": path.name,
                "sha256": _sha256(path),
            }
        )
    return {"artifactCount": len(rows), "artifacts": rows, "generatedAt": generated_at}


def generate_v47_v49_evidence(
    *,
    v46_report_dir: str | Path,
    output_dir: str | Path,
    publish_receipt: Mapping[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Write V47/V49 evidence without reading any newly reserved result interval."""

    timestamp = generated_at or _now()
    v46_root = Path(v46_report_dir).expanduser().resolve()
    root = Path(output_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    verification = _verify_v46_manifest(v46_root)
    verification.update({"generatedAt": timestamp, "sourceDirectory": v46_root.as_posix()})
    receipt = _publish_receipt(publish_receipt, timestamp)
    preregistration = _read_json(v46_root / "preregistration.json")
    policy_results = _read_json(v46_root / "policy_results.json")
    campaign_summary = _read_json(v46_root / "campaign_summary.json")
    selected_policy_id = str(campaign_summary.get("bestPolicyId") or "")
    if selected_policy_id != SELECTED_POLICY_ID:
        raise ValueError("unexpected_v46_selected_policy")

    selection_ledger, bias_audit = _selection_evidence(
        policy_results, selected_policy_id, timestamp
    )
    components = _component_manifest(preregistration)
    if components["componentCount"] != 3:
        raise ValueError("v49_requires_exactly_three_components")
    policy = _selected_policy(policy_results)
    candidate_core = {
        "candidateId": V49_CANDIDATE_ID,
        "sourceCampaignHash": preregistration.get("campaignHash"),
        "sleeves": components["components"],
        "selectedPolicy": policy,
        "allocationSemantics": "source_trade_ledger_native_risk_no_posthoc_weighting",
        "portfolioRule": "chronological_union_with_same_symbol_14_day_cooldown",
    }
    candidate_hash = stable_hash(candidate_core, prefix="portfolio_oos_candidate")
    candidate_spec = {
        **candidate_core,
        "candidateHash": candidate_hash,
        "formalStatisticalPassAllowed": False,
        "frozenAt": timestamp,
        "resultReadCount": 0,
        "status": "frozen_pre_result_read",
    }
    component_manifest = {
        **components,
        "candidateHash": candidate_hash,
        "candidateId": V49_CANDIDATE_ID,
        "frozenAt": timestamp,
    }
    portfolio_policy = {
        "candidateHash": candidate_hash,
        "candidateId": V49_CANDIDATE_ID,
        "policy": policy,
        "policyMutationAllowed": False,
        "status": "frozen",
    }
    benchmark_policy = {
        "candidateHash": candidate_hash,
        "benchmarks": [
            "each_component_standalone",
            "v46_raw_baseline_union",
            "zero_exposure",
        ],
        "resultReadCount": 0,
        "status": "frozen_pre_result_read",
    }
    oos_identity = {
        "candidateHash": candidate_hash,
        "candidateId": V49_CANDIDATE_ID,
        "frozenAt": timestamp,
        "historicalUnreadIntervalAvailable": False,
        "resultReadCount": 0,
        "routeReason": "no_provably_unread_historical_interval_registered",
        "status": "frozen_pre_result_read",
        "validationRoute": "forward_only",
    }

    outputs = {
        "v46_evidence_verification.json": verification,
        "v46_portfolio_selection_trial_ledger.json": selection_ledger,
        "v46_portfolio_selection_bias_audit.json": bias_audit,
        "v46_git_publish_receipt.json": receipt,
        "v49_portfolio_candidate_spec.json": candidate_spec,
        "v49_portfolio_component_manifest.json": component_manifest,
        "v49_portfolio_policy.json": portfolio_policy,
        "v49_portfolio_benchmark_policy.json": benchmark_policy,
        "v49_portfolio_oos_identity.json": oos_identity,
    }
    for name, payload in outputs.items():
        _write_json(root / name, payload)
    (root / "v49_portfolio_oos_access_ledger.jsonl").write_text(
        json.dumps(
            {
                "candidateHash": candidate_hash,
                "event": "identity_frozen",
                "resultReadCount": 0,
                "timestamp": timestamp,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_json(root / "artifact_manifest.json", _artifact_manifest(root, timestamp))
    return {
        "candidateHash": candidate_hash,
        "candidateId": V49_CANDIDATE_ID,
        "formalStatisticalPassAllowed": False,
        "resultReadCount": 0,
        "status": "frozen_pre_result_read",
    }
