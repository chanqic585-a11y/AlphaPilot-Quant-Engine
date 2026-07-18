"""V26 ranking-semantics closure for the frozen V25 candidate."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import hashlib
import json
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.formal_validation.candidate_ranking_registry import (
    CandidateRankingRegistry,
)


SOURCE_CANDIDATE_ID = "auto-trend_failure_reversal-4h-short-v2"
LEGACY_V25_ROUTE_CANDIDATE_ID = "auto-trend_failure-reversal-4h-short-v2"
_UNRESOLVED_FIELDS = ["eventExtremeResidualZ", "recoverySizeZ"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_hashes(root: Path) -> dict[str, str]:
    if not Path(root).exists():
        return {}
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(Path(root).rglob("*"))
        if path.is_file()
    }


def _manifest(root: Path) -> dict[str, Any]:
    artifacts = [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256(path),
            "sizeBytes": path.stat().st_size,
        }
        for path in sorted(Path(root).rglob("*"))
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    payload: dict[str, Any] = {
        "schemaVersion": "automatic_strategy_to_demo_artifact_manifest_v1",
        "artifactCount": len(artifacts),
        "artifacts": artifacts,
    }
    payload["manifestHash"] = stable_hash(
        payload, prefix="automatic_strategy_to_demo_manifest"
    )
    return payload


def build_v25_ranking_semantics_clarification_sidecar() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": "v25_ranking_semantics_clarification_sidecar_v1",
        "candidateId": SOURCE_CANDIDATE_ID,
        "authoritativeCandidateId": SOURCE_CANDIDATE_ID,
        "authoritativeIdentitySources": [
            "candidate_inventory",
            "candidate_preregistration",
            "trial_lineage",
            "real_signal_capacity_certification",
        ],
        "legacyRouteCandidateIdAlias": LEGACY_V25_ROUTE_CANDIDATE_ID,
        "candidateIdentityAliasMismatchPreserved": True,
        "capacitySemanticsResolved": True,
        "capacityCertificationPassed": True,
        "remainingFormalMissingFields": list(_UNRESOLVED_FIELDS),
        "clarifiedCurrentStatus": "formal_data_blocked_ranking_semantics",
        "oldCandidateMutable": False,
        "historicalEvidenceMutationAllowed": False,
    }
    payload["sidecarHash"] = stable_hash(
        payload, prefix="v25_ranking_semantics_clarification"
    )
    return payload


def audit_frozen_candidate_ranking_semantics(
    *,
    hypothesis: Mapping[str, Any],
    candidate: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    candidate_adapter_source: str,
    freqtrade_adapter_source: str,
    source_commit: str,
) -> dict[str, Any]:
    frozen_candidate = dict(preregistration.get("candidateSpec") or {})
    identity_consistent = (
        str(candidate.get("candidateId") or "") == SOURCE_CANDIDATE_ID
        and str(frozen_candidate.get("candidateId") or "") == SOURCE_CANDIDATE_ID
    )
    combined_source = f"{candidate_adapter_source}\n{freqtrade_adapter_source}"
    fields_in_candidate = [
        field
        for field in _UNRESOLVED_FIELDS
        if field in json.dumps(dict(candidate), sort_keys=True)
        or field in json.dumps(dict(preregistration), sort_keys=True)
    ]
    fields_in_adapter = [field for field in _UNRESOLVED_FIELDS if field in combined_source]
    derivable = identity_consistent and len(fields_in_candidate) == 2 and len(fields_in_adapter) == 2
    if derivable:
        status = "uniquely_derivable_from_frozen_entry_logic"
    else:
        status = "not_derivable_without_new_hypothesis"
    payload: dict[str, Any] = {
        "schemaVersion": "ranking_semantics_derivation_audit_v1",
        "candidateId": SOURCE_CANDIDATE_ID,
        "familyId": str(candidate.get("familyId") or hypothesis.get("familyId") or ""),
        "sourceCommit": str(source_commit),
        "status": status,
        "identityConsistent": identity_consistent,
        "frozenEntrySetupId": (candidate.get("entryDefinition") or {}).get("setupId"),
        "frozenEntryEvidence": [
            "ema_fast_span_20",
            "ema_slow_span_80",
            "prior_trend_relation",
            "closed_bar_ema_fast_reversal",
            "next_bar_open_entry",
        ],
        "requestedRankingFields": list(_UNRESOLVED_FIELDS),
        "fieldsDefinedByFrozenCandidate": fields_in_candidate,
        "fieldsDefinedByFrozenAdapters": fields_in_adapter,
        "missingFrozenDefinitions": [
            "residual_source_series",
            "residual_lookback",
            "recovery_source_series",
            "recovery_lookback",
            "normalization_formula",
        ],
        "multiplePlausibleDefinitionsExist": not derivable,
        "newHypothesisRequired": not derivable,
        "s01DefaultApplied": False,
        "formulaSearchCount": 0,
        "economicReadCount": 0,
        "exitResultReadCount": 0,
        "statisticalResultReadCount": 0,
        "lockedOosReadCount": 0,
        "formalClaimCount": 0,
        "formalAttemptCount": 0,
        "formalResultCount": 0,
        "formalResultReadCount": 0,
        "prohibitedOperationsObserved": [],
    }
    payload["auditHash"] = stable_hash(
        payload, prefix="ranking_semantics_derivation_audit"
    )
    return payload


def resolve_current_candidate(audit: Mapping[str, Any]) -> dict[str, Any]:
    unique = audit.get("status") == "uniquely_derivable_from_frozen_entry_logic"
    payload: dict[str, Any] = {
        "schemaVersion": "v26_current_candidate_resolution_v1",
        "sourceCandidateId": SOURCE_CANDIDATE_ID,
        "derivationAuditHash": audit.get("auditHash"),
        "candidateStatus": (
            "eligible_for_single_preregistered_structural_revision"
            if unique
            else "closed_current_candidate_ranking_semantics_not_derivable"
        ),
        "nextStage": (
            "v26_build_v3_ranking_contract"
            if unique
            else "v27_new_candidate_research"
        ),
        "structuralRevisionBudgetConsumed": 0,
        "formalLedger": {
            "claimCount": 0,
            "attemptCount": 0,
            "resultCount": 0,
            "resultReadCount": 0,
        },
        "lockedOosReadCount": 0,
        "releaseCount": 0,
        "approvalCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    payload["resolutionHash"] = stable_hash(
        payload, prefix="v26_current_candidate_resolution"
    )
    return payload


def _audit_markdown(audit: Mapping[str, Any]) -> str:
    missing = ", ".join(str(value) for value in audit["missingFrozenDefinitions"])
    return (
        "# V26 Ranking Semantics Derivation Audit\n\n"
        f"- Candidate: `{audit['candidateId']}`\n"
        f"- Status: `{audit['status']}`\n"
        f"- Source commit: `{audit['sourceCommit']}`\n"
        f"- Missing frozen definitions: {missing}\n"
        "- Economic, exit, statistical, and Locked OOS reads: `0`\n"
        "- Decision: close the v2 replay path and continue with V27; no formula guessing.\n"
    )


def run_v26_semantic_closure(
    *,
    repo_root: Path,
    reports_root: Path,
    source_program_root: Path,
    prompt_hash: str,
    quant_baseline_commit: str,
    console_baseline_commit: str,
    docs_baseline_commit: str,
    source_commit: str,
    generated_at: str,
    hypothesis: Mapping[str, Any],
    candidate: Mapping[str, Any],
    preregistration: Mapping[str, Any],
    candidate_adapter_source: str,
    freqtrade_adapter_source: str,
) -> dict[str, Any]:
    del repo_root
    source_before = _tree_hashes(Path(source_program_root))
    identity = {
        "promptHash": str(prompt_hash),
        "quantBaselineCommit": str(quant_baseline_commit),
        "consoleBaselineCommit": str(console_baseline_commit),
        "docsBaselineCommit": str(docs_baseline_commit),
        "sourceProgramId": "automatic_strategy_demo_f57c443abeaf06c0",
        "sourceCandidateId": SOURCE_CANDIDATE_ID,
    }
    identity_hash = stable_hash(identity, prefix="automatic_strategy_to_demo_v26")
    program_id = f"automatic_strategy_to_demo_v26_{identity_hash.rsplit('_', 1)[-1][:16]}"
    root = Path(reports_root) / "automatic_strategy_to_demo" / program_id
    v26_root = root / "v26"
    v26_root.mkdir(parents=True, exist_ok=True)

    spec: dict[str, Any] = {
        "schemaVersion": "automatic_strategy_to_demo_master_program_v1",
        "programId": program_id,
        "identity": identity,
        "targetRGateMode": "advisory",
        "minimumTargetR": None,
        "economicGatesRemainHard": True,
        "resultDrivenRelaxationAllowed": False,
        "maxCampaigns": 3,
        "maxFamiliesPerCampaign": 8,
        "maxVariantsPerFamily": 2,
        "maxCandidatesPerCampaign": 16,
        "maxFormalCandidatesPerCampaign": 6,
        "maxAdditionalFullBacktests": 143,
        "exactReleaseApprovalRequired": True,
        "liveEnabled": False,
        "withdrawEnabled": False,
    }
    spec["programSpecHash"] = stable_hash(spec, prefix="master_program_spec")
    audit = audit_frozen_candidate_ranking_semantics(
        hypothesis=hypothesis,
        candidate=candidate,
        preregistration=preregistration,
        candidate_adapter_source=candidate_adapter_source,
        freqtrade_adapter_source=freqtrade_adapter_source,
        source_commit=source_commit,
    )
    resolution = resolve_current_candidate(audit)
    sidecar = build_v25_ranking_semantics_clarification_sidecar()
    registry = CandidateRankingRegistry().manifest()
    baseline = {"schemaVersion": "master_baseline_identity_v1", **identity}
    baseline["baselineIdentityHash"] = stable_hash(
        baseline, prefix="master_baseline_identity"
    )
    budget = {
        "schemaVersion": "automatic_strategy_to_demo_budget_v1",
        "campaignsConsumed": 0,
        "candidateTrialsConsumed": 0,
        "structuralRevisionsConsumed": 0,
        "formalClaimsConsumed": 0,
        "formalAttemptsConsumed": 0,
        "formalResultsRead": 0,
        "lockedOosReads": 0,
        "releaseCount": 0,
        "approvalCount": 0,
        "orderCount": 0,
    }
    state = {
        "schemaVersion": "automatic_strategy_to_demo_program_state_v1",
        "programId": program_id,
        "stage": (
            "v26_completed_route_v27"
            if resolution["nextStage"] == "v27_new_candidate_research"
            else "v26_completed_route_v3"
        ),
        "nextAllowedStage": resolution["nextStage"],
        "terminalRoute": None,
        "humanGateStatus": "not_required",
        "generatedAt": generated_at,
        "formalRunCount": 0,
        "resultReadCount": 0,
        "lockedOosReadCount": 0,
        "releaseCount": 0,
        "approvalCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    ledger_event = {
        "schemaVersion": "automatic_strategy_to_demo_ledger_event_v1",
        "eventType": "v26_semantic_closure_completed",
        "createdAt": generated_at,
        "programId": program_id,
        "stage": state["stage"],
        "auditHash": audit["auditHash"],
        "resolutionHash": resolution["resolutionHash"],
    }
    source_after = _tree_hashes(Path(source_program_root))
    mutation_count = sum(
        source_before.get(path) != source_after.get(path)
        for path in set(source_before) | set(source_after)
    )
    resolution["historicalArtifactMutationCount"] = mutation_count
    if mutation_count:
        raise RuntimeError("historical_v25_artifact_mutation_detected")

    for path, payload in (
        (root / "program_spec.json", spec),
        (root / "program_state.json", state),
        (root / "program_budget.json", budget),
        (root / "baseline_identity.json", baseline),
        (root / "v25_ranking_semantics_clarification_sidecar.json", sidecar),
        (v26_root / "v25_ranking_semantics_clarification_sidecar.json", sidecar),
        (root / "candidate_ranking_registry.json", registry),
        (root / "ranking_semantics_derivation_audit.json", audit),
        (v26_root / "ranking_semantics_derivation_audit.json", audit),
        (root / "current_candidate_resolution.json", resolution),
    ):
        write_json_atomic(path, payload)
    (root / "ranking_semantics_derivation_audit.md").write_text(
        _audit_markdown(audit), encoding="utf-8"
    )
    (root / "program_ledger.jsonl").write_text(
        json.dumps(ledger_event, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (root / "program_budget_ledger.jsonl").write_text(
        json.dumps(
            {
                "eventType": "v26_budget_snapshot",
                "createdAt": generated_at,
                "budget": budget,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    write_json_atomic(root / "artifact_manifest.json", _manifest(root))
    return {
        "programId": program_id,
        "status": "completed",
        "stage": state["stage"],
        "nextAllowedStage": state["nextAllowedStage"],
        "artifactRoot": str(root),
        "formalRunCount": 0,
        "resultReadCount": 0,
        "lockedOosReadCount": 0,
    }


__all__ = [
    "audit_frozen_candidate_ranking_semantics",
    "build_v25_ranking_semantics_clarification_sidecar",
    "resolve_current_candidate",
    "run_v26_semantic_closure",
]
