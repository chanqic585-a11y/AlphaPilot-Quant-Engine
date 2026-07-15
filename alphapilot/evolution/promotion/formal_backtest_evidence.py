"""Fail-closed validation for Phase 3C formal backtest evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from alphapilot.evolution.registry.hashing import stable_hash


@dataclass(frozen=True)
class FormalBacktestEvidenceValidation:
    passed: bool
    failedCheckIds: tuple[str, ...]
    normalized: dict[str, Any]


def _candidate_by_id(preregistration: Mapping[str, Any], candidate_id: str) -> Mapping[str, Any] | None:
    candidates = preregistration.get("candidates")
    if not isinstance(candidates, list):
        return None
    matches = [row for row in candidates if isinstance(row, Mapping) and row.get("candidateId") == candidate_id]
    return matches[0] if len(matches) == 1 else None


def _roles(value: Any) -> dict[str, list[str]]:
    source = value if isinstance(value, Mapping) else {}
    return {
        "confirmation": sorted(str(item) for item in source.get("confirmation", []) if item),
        "ranking": sorted(str(item) for item in source.get("ranking", []) if item),
        "veto": sorted(str(item) for item in source.get("veto", []) if item),
    }


def _candidate_roles(candidate: Mapping[str, Any]) -> dict[str, list[str]]:
    return {
        "confirmation": sorted(str(item) for item in candidate.get("factorConfirmations", []) if item),
        "ranking": sorted(str(item) for item in candidate.get("factorRanking", []) if item),
        "veto": sorted(str(item) for item in candidate.get("factorVetoes", []) if item),
    }


def validate_formal_backtest_evidence(
    evidence: Mapping[str, Any],
    *,
    preregistration: Mapping[str, Any],
    campaign_summary: Mapping[str, Any],
    artifact_manifest: Mapping[str, Any],
) -> FormalBacktestEvidenceValidation:
    """Validate lineage, holdout, folds, costs, factors, and formal status.

    Local simulation, shadow observations, engineering smoke tests, and legacy
    Demo history are intentionally ignored. Missing evidence therefore fails.
    """

    failures: list[str] = []

    def check(check_id: str, passed: bool) -> None:
        if not passed:
            failures.append(check_id)

    candidate_id = str(evidence.get("candidateId") or "")
    candidate = _candidate_by_id(preregistration, candidate_id)
    gate = evidence.get("gateEvidence") if isinstance(evidence.get("gateEvidence"), Mapping) else {}
    formal_gates = gate.get("formalGates") if isinstance(gate.get("formalGates"), Mapping) else {}
    oos_metrics = gate.get("oosMetrics") if isinstance(gate.get("oosMetrics"), Mapping) else {}
    folds = oos_metrics.get("folds") if isinstance(oos_metrics.get("folds"), Mapping) else {}
    evidence_roles = _roles(evidence.get("factorRoles"))
    factor_hashes = sorted(str(item) for item in evidence.get("factorDefinitionHashes", []) if item)
    role_hashes = sorted({item for values in evidence_roles.values() for item in values})

    check("schema_version", evidence.get("schemaVersion") == "phase3c_formal_pass_evidence_v1")
    check("formal_pass", evidence.get("formalPass") is True)
    check("campaign_id", bool(candidate_id) and evidence.get("campaignId") == preregistration.get("campaignId") == campaign_summary.get("campaignId") == artifact_manifest.get("campaignId"))
    check("campaign_formal_count", int(campaign_summary.get("formalPassCount") or 0) > 0)
    check("preregistration_hash", evidence.get("preregistrationHash") == preregistration.get("preregistrationHash"))
    check("candidate_registered", candidate is not None)
    if candidate is not None:
        check("candidate_definition_hash", evidence.get("candidateDefinitionHash") == candidate.get("definitionHash"))
        check("market_mechanism_id", evidence.get("marketMechanismId") == candidate.get("marketMechanismId"))
        check("factor_roles", evidence_roles == _candidate_roles(candidate))
    check("external_reference_manifest_hash", evidence.get("externalReferenceManifestHash") == preregistration.get("externalReferenceManifestHash"))
    check("data_snapshot_hash", evidence.get("dataSnapshotHash") == preregistration.get("dataSnapshotHash") == campaign_summary.get("dataSnapshotHash", preregistration.get("dataSnapshotHash")))
    check("factor_registry_hash", evidence.get("factorRegistryHash") == preregistration.get("factorRegistryHash"))
    check("factor_shortlist_hash", evidence.get("factorShortlistHash") == preregistration.get("factorShortlistHash"))
    check("factor_definition_hashes", factor_hashes == role_hashes)
    check("formal_gate_hash", evidence.get("formalGateHash") == stable_hash(gate, prefix="formal_gate"))
    check("sample_gate", gate.get("samplePassed") is True)
    check("prescreen_gate", gate.get("prescreenPassed") is True)
    check("base_gate", gate.get("basePassed") is True)
    check("formal_gate", gate.get("formalPassed") is True)
    check("walk_forward_folds", len(folds) >= 5)
    required_formal_gates = {
        "holdoutAccessBeforeFinalEvaluation",
        "oosProfitFactor",
        "oosAverageNetR",
        "stress1_5xProfitFactor",
        "stress1_5xAverageNetR",
        "positiveFoldCount",
    }
    check(
        "formal_gate_set",
        required_formal_gates.issubset(formal_gates)
        and all(isinstance(formal_gates[name], Mapping) and formal_gates[name].get("passed") is True for name in required_formal_gates),
    )
    holdout_gate = formal_gates.get("holdoutAccessBeforeFinalEvaluation", {})
    check("holdout_locked", isinstance(holdout_gate, Mapping) and holdout_gate.get("observed") == 0)
    check("artifact_manifest_hash", bool(artifact_manifest.get("manifestHash")))

    normalized = dict(evidence)
    normalized["factorDefinitionHashes"] = factor_hashes
    normalized["factorRoles"] = evidence_roles
    normalized["backtestReportHash"] = artifact_manifest.get("manifestHash")
    normalized["costModelHash"] = stable_hash(preregistration.get("costScenarios", {}), prefix="cost_model")
    normalized["formalGateHash"] = stable_hash(gate, prefix="formal_gate")
    return FormalBacktestEvidenceValidation(
        passed=not failures,
        failedCheckIds=tuple(failures),
        normalized=normalized,
    )
