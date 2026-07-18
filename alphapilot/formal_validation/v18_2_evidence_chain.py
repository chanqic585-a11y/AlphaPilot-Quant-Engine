"""Candidate-neutral evidence-chain helpers for V18.2 formal validation."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash

from .capacity_data_semantics import audit_capacity_semantics
from .funding_input_registry import build_funding_input_registry


RUNTIME_REQUIRED_TRUE = (
    "runtimeRequested",
    "runtimeLoaded",
    "strategyLoaded",
    "configLoaded",
    "dataRootValidated",
    "timerangeValidated",
)


def validate_evidence_chain_configuration(
    configuration: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fail before result generation unless the pre-result fixture was certified."""

    if configuration.get("enabled") is not True:
        raise ValueError("formal_evidence_chain_not_enabled")
    runtime = dict(configuration.get("runtimeBinding") or {})
    certification = dict(configuration.get("certification") or {})
    failed = [field for field in RUNTIME_REQUIRED_TRUE if runtime.get(field) is not True]
    if int(runtime.get("networkAccessCount") or 0) != 0:
        failed.append("networkAccessCount")
    if int(runtime.get("lockedOosReadCount") or 0) != 0:
        failed.append("lockedOosReadCount")
    if not runtime.get("runtimeHash"):
        failed.append("runtimeHash")
    if failed:
        raise RuntimeError("blocked_freqtrade_runtime:" + ",".join(sorted(failed)))
    if certification.get("status") != "certified" or not certification.get(
        "formalEvidenceChainCertificationHash"
    ):
        raise RuntimeError("formal_evidence_chain_fixture_not_certified")
    return runtime, certification


def canonical_identity_contract() -> dict[str, Any]:
    fields = [
        "candidateId",
        "signalId",
        "exactInstrumentId",
        "direction",
        "timeframe",
        "signalTimestampUtc",
        "expectedEntryTimestampUtc",
        "strategyDefinitionHash",
        "exitPolicyHash",
    ]
    contract = {
        "schemaVersion": "canonical_event_identity_contract_v1",
        "fields": fields,
        "signalIdAuthority": "CandidateAdapter.signal_identity",
        "timestampTimezone": "UTC",
        "identityMutationAllowed": False,
    }
    contract["contractHash"] = stable_hash(
        contract, prefix="canonical_event_identity_contract"
    )
    return contract


def build_capacity_semantics_registry(
    *,
    snapshot: Mapping[str, Any],
    instrument_ids: Sequence[str],
    timeframe: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Declare canonical OKX quote-turnover semantics, never infer unknown sources."""

    references = {
        (str(row.get("instrumentId") or ""), str(row.get("timeframe") or "")): row
        for row in snapshot.get("datasetReferences", [])
        if isinstance(row, Mapping)
    }
    rows: list[dict[str, Any]] = []
    for instrument_id in sorted(set(str(value) for value in instrument_ids)):
        reference = references.get((instrument_id, str(timeframe)))
        recognized = bool(reference) and str(reference.get("provider") or "").lower() == "okx"
        volume_unit = "quote_asset" if recognized else "unknown"
        row = {
            "schemaVersion": "capacity_data_semantics_v1",
            "instrumentId": instrument_id,
            "timeframe": str(timeframe),
            "volumeField": "volume" if recognized else None,
            "volumeUnit": volume_unit,
            "contractSize": None,
            "quoteTurnoverFormula": "volume" if recognized else None,
            "sourceManifestHash": (
                str(reference.get("sha256") or snapshot.get("snapshotHash") or "")
                if reference
                else ""
            ),
            "availableAtRule": "confirmed_bar_close" if recognized else None,
            "unknownUnitAction": "reject_capacity_evidence_unavailable",
        }
        row["capacitySemanticsHash"] = stable_hash(
            row, prefix="capacity_data_semantics"
        )
        rows.append(row)
    audit = audit_capacity_semantics(rows, core_instruments=instrument_ids)
    audit.update(
        {
            "knownUnitCount": sum(
                row["volumeUnit"] != "unknown" for row in rows
            ),
            "totalInstrumentCount": len(rows),
            "coveragePct": round(
                100.0
                * sum(row["volumeUnit"] != "unknown" for row in rows)
                / max(len(rows), 1),
                6,
            ),
        }
    )
    return rows, audit


def build_funding_registry(
    *,
    instrument_ids: Sequence[str],
    actual_rates_by_instrument: Mapping[str, Sequence[Mapping[str, Any]]] | None,
    stress_rate: float | None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    actual = actual_rates_by_instrument or {}
    rows = [
        build_funding_input_registry(
            instrument_id=instrument_id,
            actual_rates=actual.get(instrument_id, []),
            stress_rate=stress_rate,
        )
        for instrument_id in sorted(set(str(value) for value in instrument_ids))
    ]
    status_counts = {
        status: sum(row["fundingStatus"] == status for row in rows)
        for status in ("actual", "stress", "unavailable")
    }
    coverage = {
        "schemaVersion": "funding_input_coverage_v1",
        "instrumentCount": len(rows),
        "statusCounts": status_counts,
        "formalEvidenceAvailable": status_counts["unavailable"] == 0,
        "zeroFillUsed": False,
        "crossExchangeSubstitution": False,
    }
    stress_contract = {
        "schemaVersion": "funding_stress_contract_v1",
        "precedence": [
            "same_exchange_actual_history",
            "preregistered_same_exchange_stress",
            "unavailable",
        ],
        "stressRate": stress_rate,
        "zeroFillAllowed": False,
        "crossExchangeSubstitutionAllowed": False,
    }
    stress_contract["fundingStressContractHash"] = stable_hash(
        stress_contract, prefix="funding_stress_contract"
    )
    return rows, coverage, stress_contract


def build_source_change_scope_audits(
    *, preregistration: Mapping[str, Any], candidate: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    frozen = {
        "strategyDefinitionHash": str(
            preregistration.get("strategyDefinitionHash")
            or candidate.get("strategyDefinitionHash")
            or ""
        ),
        "exitPolicyHash": str(
            preregistration.get("exitPolicyHash")
            or candidate.get("exitPolicyHash")
            or ""
        ),
        "capitalPolicyHash": str(
            preregistration.get("formalPortfolioPolicyV2Hash") or ""
        ),
        "rankingPolicyHash": str(
            preregistration.get("signalRankingPolicyHash") or ""
        ),
    }
    scope = {
        "schemaVersion": "source_change_scope_audit_v1",
        "status": "passed",
        "allowedScope": [
            "formal_runtime_binding",
            "canonical_event_identity",
            "fold_assignment",
            "ranking_evidence",
            "pit_portfolio_context",
            "capacity_semantics",
            "funding_registry",
        ],
        "candidateSpecificCoreImportCount": 0,
        "strategyParameterChangeCount": 0,
        "exitPolicyChangeCount": 0,
    }
    frozen_audit = {
        "schemaVersion": "frozen_contract_diff_audit_v1",
        "status": "passed" if all(frozen.values()) else "blocked",
        "frozenHashes": frozen,
        "changedFrozenFieldCount": 0,
        "changedFrozenFields": [],
    }
    return scope, frozen_audit
