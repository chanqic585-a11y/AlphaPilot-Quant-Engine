"""Generate immutable, unapproved strategy-validation Demo releases."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import canonical_json, stable_hash

from .demo_risk_profile import validate_demo_risk_profile
from .formal_backtest_evidence import validate_formal_backtest_evidence


def _candidate_map(preregistration: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = preregistration.get("candidates")
    if not isinstance(rows, list):
        return {}
    result: dict[str, Mapping[str, Any]] = {}
    duplicates: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        candidate_id = str(row.get("candidateId") or "")
        if not candidate_id:
            continue
        if candidate_id in result:
            duplicates.add(candidate_id)
        result[candidate_id] = row
    for candidate_id in duplicates:
        result.pop(candidate_id, None)
    return result


def _ranking(evidence: Mapping[str, Any]) -> tuple[Any, ...]:
    gate = evidence["gateEvidence"]
    oos = gate.get("oosMetrics", {})
    stress = gate.get("stress1_5xMetrics", {})
    return (
        -float(oos.get("profitFactor") or 0),
        -float(oos.get("averageNetR") or 0),
        -float(stress.get("profitFactor") or 0),
        -int(oos.get("positiveFoldCount") or 0),
        float(oos.get("maximumDrawdownPct") or float("inf")),
        str(evidence["candidateId"]),
    )


def _release_payload(
    *,
    evidence: Mapping[str, Any],
    candidate: Mapping[str, Any],
    risk_profile: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    body = {
        "schemaVersion": "strategy_validation_release_v1",
        "campaignId": evidence["campaignId"],
        "candidateId": evidence["candidateId"],
        "strategyId": evidence["candidateId"],
        "strategyFamilyId": candidate["familyId"],
        "marketMechanismId": evidence["marketMechanismId"],
        "strategyDefinitionHash": evidence["candidateDefinitionHash"],
        "externalReferenceManifestHash": evidence["externalReferenceManifestHash"],
        "dataSnapshotHash": evidence["dataSnapshotHash"],
        "factorRegistryHash": evidence["factorRegistryHash"],
        "factorShortlistHash": evidence["factorShortlistHash"],
        "factorDefinitionHashes": list(evidence["factorDefinitionHashes"]),
        "factorRoles": dict(evidence["factorRoles"]),
        "preregistrationHash": evidence["preregistrationHash"],
        "costModelHash": evidence["costModelHash"],
        "riskConfigHash": risk_profile["riskConfigHash"],
        "riskProfile": dict(risk_profile),
        "backtestReportHash": evidence["backtestReportHash"],
        "formalGateHash": evidence["formalGateHash"],
        "releasePurpose": "strategy_forward_validation",
        "evidenceClass": "demo_strategy_validation",
        "environment": "demo",
        "approvalRequired": True,
        "approved": False,
        "immutable": True,
        "createdAt": created_at,
    }
    release_hash = stable_hash(body, prefix="strategy_validation_release")
    return {
        **body,
        "releaseId": stable_hash({"releaseHash": release_hash}, prefix="validation_release"),
        "releaseHash": release_hash,
    }


def build_strategy_validation_releases(
    *,
    evidences: Sequence[Mapping[str, Any]],
    preregistration: Mapping[str, Any],
    campaign_summary: Mapping[str, Any],
    artifact_manifest: Mapping[str, Any],
    risk_profile: Mapping[str, Any],
    created_at: str,
    maximum_releases: int = 3,
) -> list[dict[str, Any]]:
    if maximum_releases < 0 or maximum_releases > 3:
        raise ValueError("maximum_releases must be between 0 and 3")
    validate_demo_risk_profile(risk_profile)
    candidates = _candidate_map(preregistration)
    eligible: list[dict[str, Any]] = []
    for evidence in evidences:
        validation = validate_formal_backtest_evidence(
            evidence,
            preregistration=preregistration,
            campaign_summary=campaign_summary,
            artifact_manifest=artifact_manifest,
        )
        candidate = candidates.get(str(evidence.get("candidateId") or ""))
        if validation.passed and candidate is not None:
            eligible.append(validation.normalized)
    eligible.sort(key=_ranking)
    return [
        _release_payload(
            evidence=evidence,
            candidate=candidates[str(evidence["candidateId"])],
            risk_profile=risk_profile,
            created_at=created_at,
        )
        for evidence in eligible[:maximum_releases]
    ]


def write_strategy_validation_releases(releases: Sequence[Mapping[str, Any]], output_dir: Path) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for release in releases:
        path = output / f"{release['releaseHash']}.json"
        expected = canonical_json(release).encode("utf-8")
        if path.exists():
            if path.read_bytes() != expected:
                raise FileExistsError(f"hash-addressed release conflict: {path.name}")
        else:
            path.write_bytes(expected)
        paths.append(path)
    return paths
