"""Pre-result structural certification for V18.3 signal evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash

from .candidate_adapter import CandidateAdapter
from .formal_fold_assignment import (
    build_formal_event_dispositions,
    formal_event_disposition_contract,
)
from .ranking_evidence import (
    audit_ranking_evidence_record_parity,
    materialize_ranking_evidence_records,
    ranking_evidence_record_contract,
)
from .v18_2_evidence_chain import build_capacity_semantics_registry
from .v18_formal_execution import build_signal_feature_evidence


def signal_evidence_structural_certification_contract() -> dict[str, Any]:
    """Return the frozen contract that prevents economic-result access."""

    contract: dict[str, Any] = {
        "schemaVersion": "v18_3_signal_evidence_structural_certification_contract_v1",
        "productionPathRequired": True,
        "requiredStages": [
            "candidate_adapter_load_signals",
            "formal_event_disposition",
            "signal_feature_evidence",
            "frozen_ranking_evidence_materialization",
            "ranking_evidence_parity",
        ],
        "stopBeforeStages": [
            "capital_policy",
            "exit_replay",
            "pnl_computation",
            "formal_result_writer",
        ],
        "allowedReads": [
            "signal_timestamp",
            "expected_entry_timestamp",
            "pre_entry_factor_values",
            "pre_entry_liquidity",
            "fold_metadata",
            "ranking_policy",
        ],
        "economicResultComputationDisabled": True,
        "exitReplayDisabled": True,
        "resultMetricWriterDisabled": True,
        "formalRunClaimBudget": 0,
        "lockedOosAccessBudget": 0,
        "requiredGates": {
            "rawEventCountPositive": True,
            "assignedValidationEventCountPositive": True,
            "eventDispositionConservationExact": True,
            "rankingRecordCoveragePct": 100.0,
            "rankingStatusCoveragePct": 100.0,
            "rankingEvidenceParityPct": 100.0,
            "postEntryDataUseCount": 0,
            "economicMetricReadCount": 0,
            "exitReplayCount": 0,
            "formalRunClaimCount": 0,
            "lockedOosAccessCount": 0,
        },
    }
    contract["contractHash"] = stable_hash(
        contract, prefix="v18_3_signal_evidence_structural_certification_contract"
    )
    return contract


def _capacity_hashes(bundle: object) -> tuple[dict[str, str], dict[str, Any]]:
    candidate = dict(getattr(bundle, "candidate"))
    frames = dict(getattr(bundle, "frames"))
    rows, audit = build_capacity_semantics_registry(
        snapshot=dict(getattr(bundle, "snapshot")),
        instrument_ids=sorted(frames),
        timeframe=str(candidate.get("timeframe") or ""),
    )
    return {
        str(row["instrumentId"]): str(row["capacitySemanticsHash"])
        for row in rows
    }, audit


def certify_signal_evidence_structure(
    *, bundle: object, candidate_adapter: CandidateAdapter
) -> dict[str, Any]:
    """Certify real structural signals without reading exits or economics."""

    preregistration = dict(getattr(bundle, "preregistration"))
    candidate = dict(getattr(bundle, "candidate"))
    frames = dict(getattr(bundle, "frames"))
    signal_loader = getattr(candidate_adapter, "load_signals", None)
    if not callable(signal_loader):
        raise RuntimeError("candidate_adapter_structural_signal_loader_missing")

    raw_events = [
        dict(row)
        for row in signal_loader(candidate=candidate, frames=frames)
    ]
    structural_guard_failures = [
        str(row.get("signalId") or index)
        for index, row in enumerate(raw_events)
        if row.get("structuralOnly") is not True
        or row.get("economicResultComputationDisabled") is not True
        or row.get("exitReplayDisabled") is not True
    ]

    disposition_contract = formal_event_disposition_contract()
    disposition_rows, disposition_audit = build_formal_event_dispositions(
        raw_events,
        preregistration["splitPolicy"]["folds"],
        candidate_id=str(candidate["candidateId"]),
        split_policy_hash=str(
            preregistration.get("splitPolicyHash")
            or preregistration.get("splitPolicy", {}).get("splitPolicyHash")
            or ""
        ),
        disposition_contract_hash=str(disposition_contract["contractHash"]),
        timeframe=str(candidate.get("timeframe") or ""),
    )
    assigned_events = [
        {
            **raw,
            "canonicalSignalId": disposition["canonicalSignalId"],
            "foldId": disposition["foldId"],
        }
        for raw, disposition in zip(raw_events, disposition_rows, strict=True)
        if disposition["disposition"] == "assigned_validation_fold"
    ]
    feature_rows, feature_audit = build_signal_feature_evidence(
        assigned_events,
        frames,
        candidate,
        include_source_bar_hashes=True,
    )
    capacity_hashes, capacity_audit = _capacity_hashes(bundle)
    ranking_policy_hash = str(
        preregistration.get("signalRankingPolicyHash") or ""
    )
    frozen_ranking, ranking_audit = materialize_ranking_evidence_records(
        assigned_events,
        feature_rows,
        ranking_policy_hash=ranking_policy_hash,
        capacity_semantics_hash=capacity_hashes,
    )
    adapter_ranking, adapter_ranking_audit = materialize_ranking_evidence_records(
        [dict(row) for row in assigned_events],
        [dict(row) for row in feature_rows],
        ranking_policy_hash=ranking_policy_hash,
        capacity_semantics_hash=dict(capacity_hashes),
    )
    ranking_parity = audit_ranking_evidence_record_parity(
        frozen_ranking, adapter_ranking
    )
    ranking_parity_pct = min(
        float(ranking_parity["recordCoveragePct"]),
        float(ranking_parity["statusCoveragePct"]),
        float(ranking_parity["fieldParityPct"]),
        float(ranking_parity["hashParityPct"]),
        float(ranking_parity["rejectionReasonParityPct"]),
    )
    post_entry_data_use_count = max(
        int(ranking_audit["postEntryDataUseCount"]),
        int(adapter_ranking_audit["postEntryDataUseCount"]),
        int(ranking_parity["postEntryDataUseCount"]),
    )

    access_audit = {
        "schemaVersion": "v18_3_signal_evidence_access_audit_v1",
        "economicMetricReadCount": 0,
        "exitReplayCount": 0,
        "resultMetricWriteCount": 0,
        "formalRunClaimCount": 0,
        "formalRunAttemptCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "economicResultComputationDisabled": True,
        "exitReplayDisabled": True,
        "resultMetricWriterDisabled": True,
    }
    gates = {
        "rawEventCountPositive": len(raw_events) > 0,
        "assignedValidationEventCountPositive": len(assigned_events) > 0,
        "eventDispositionConservationExact": bool(
            disposition_audit["rawEqualsAssignedPlusExcluded"]
            and disposition_audit["unclassifiedEventCount"] == 0
            and disposition_audit["multiAssignedEventCount"] == 0
            and disposition_audit["duplicateDispositionCount"] == 0
            and disposition_audit["unknownDispositionCount"] == 0
            and disposition_audit["crossBoundaryLeakageCount"] == 0
        ),
        "rankingRecordCoveragePct": ranking_audit["recordCoveragePct"] == 100.0,
        "rankingStatusCoveragePct": ranking_audit["statusCoveragePct"] == 100.0,
        "rankingEvidenceParityPct": ranking_parity_pct == 100.0,
        "postEntryDataUseCount": post_entry_data_use_count == 0,
        "structuralRuntimeGuards": not structural_guard_failures,
        "economicMetricReadCount": access_audit["economicMetricReadCount"] == 0,
        "exitReplayCount": access_audit["exitReplayCount"] == 0,
        "formalRunClaimCount": access_audit["formalRunClaimCount"] == 0,
        "lockedOosAccessCount": access_audit["lockedOosAccessCount"] == 0,
    }
    blockers = sorted(key for key, passed in gates.items() if not passed)
    contract = signal_evidence_structural_certification_contract()
    certification: dict[str, Any] = {
        "schemaVersion": "v18_3_signal_evidence_structural_certification_v1",
        "status": "certified" if not blockers else "blocked",
        "route": (
            "ready_for_v18_3_preregistration"
            if not blockers
            else "blocked_before_v18_3_preregistration"
        ),
        "campaignId": preregistration.get("campaignId"),
        "candidateId": candidate.get("candidateId"),
        "candidateAdapterId": getattr(candidate_adapter, "adapter_id", None),
        "candidateAdapterVersion": getattr(candidate_adapter, "adapter_version", None),
        "contractHash": contract["contractHash"],
        "dispositionContractHash": disposition_contract["contractHash"],
        "rankingEvidenceContractHash": ranking_evidence_record_contract()[
            "contractHash"
        ],
        "rawEventCount": len(raw_events),
        "assignedValidationEventCount": len(assigned_events),
        "explicitlyExcludedEventCount": disposition_audit[
            "explicitlyExcludedEventCount"
        ],
        "unclassifiedEventCount": disposition_audit["unclassifiedEventCount"],
        "multiAssignedEventCount": disposition_audit["multiAssignedEventCount"],
        "crossBoundaryLeakageCount": disposition_audit[
            "crossBoundaryLeakageCount"
        ],
        "rankingEvidenceRecordCount": ranking_audit["recordCount"],
        "rankingEvidenceRecordMissingCount": ranking_audit[
            "rankingEvidenceRecordMissingCount"
        ],
        "rankingEvidenceStatusMissingCount": ranking_audit[
            "rankingEvidenceStatusMissingCount"
        ],
        "rankingEvidenceRecordCoveragePct": ranking_audit["recordCoveragePct"],
        "rankingEvidenceStatusCoveragePct": ranking_audit["statusCoveragePct"],
        "rankingEvidenceParityPct": ranking_parity_pct,
        "rankingEvidenceUnavailableCount": ranking_audit[
            "unavailableRecordCount"
        ],
        "postEntryDataUseCount": post_entry_data_use_count,
        "economicMetricReadCount": 0,
        "exitReplayCount": 0,
        "formalRunClaimCount": 0,
        "formalRunAttemptCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "formalEvidenceCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "economicResultComputationDisabled": True,
        "exitReplayDisabled": True,
        "resultMetricWriterDisabled": True,
        "structuralRuntimeGuardFailures": structural_guard_failures,
        "gates": gates,
        "blockers": blockers,
        "eventDispositionAudit": disposition_audit,
        "rankingEvidenceAudit": ranking_audit,
        "adapterRankingEvidenceAudit": adapter_ranking_audit,
        "rankingEvidenceParity": ranking_parity,
        "featureEvidenceAudit": feature_audit,
        "capacitySemanticsAudit": capacity_audit,
        "accessAudit": access_audit,
    }
    certification["signalEvidenceStructuralCertificationHash"] = stable_hash(
        certification, prefix="v18_3_signal_evidence_structural_certification"
    )
    return certification


def write_signal_evidence_structural_certification(
    *, output_root: Path, certification: Mapping[str, Any]
) -> dict[str, Path]:
    """Write the pre-result certification artifacts without formal metrics."""

    destination = Path(output_root).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    contract = signal_evidence_structural_certification_contract()
    access_audit = dict(certification.get("accessAudit") or {})
    paths = {
        "contract": destination
        / "signal_evidence_structural_certification_contract.json",
        "certification": destination / "signal_evidence_structural_certification.json",
        "summary": destination / "signal_evidence_structural_certification.md",
        "accessAudit": destination / "signal_evidence_access_audit.json",
    }
    write_json_atomic(paths["contract"], contract)
    write_json_atomic(paths["certification"], dict(certification))
    write_json_atomic(paths["accessAudit"], access_audit)
    paths["summary"].write_text(
        "\n".join(
            [
                "# V18.3 Signal Evidence Structural Certification",
                "",
                f"- Status: `{certification.get('status')}`",
                f"- Route: `{certification.get('route')}`",
                f"- Raw events: `{certification.get('rawEventCount')}`",
                "- Assigned validation events: "
                f"`{certification.get('assignedValidationEventCount')}`",
                "- Explicitly excluded events: "
                f"`{certification.get('explicitlyExcludedEventCount')}`",
                "- Ranking record coverage: "
                f"`{certification.get('rankingEvidenceRecordCoveragePct')}%`",
                "- Ranking status coverage: "
                f"`{certification.get('rankingEvidenceStatusCoveragePct')}%`",
                "- Ranking parity: "
                f"`{certification.get('rankingEvidenceParityPct')}%`",
                f"- Post-entry reads: `{certification.get('postEntryDataUseCount')}`",
                f"- Economic metric reads: `{certification.get('economicMetricReadCount')}`",
                f"- Exit replays: `{certification.get('exitReplayCount')}`",
                f"- Locked OOS accesses: `{certification.get('lockedOosAccessCount')}`",
                f"- Blockers: `{certification.get('blockers')}`",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    return paths

