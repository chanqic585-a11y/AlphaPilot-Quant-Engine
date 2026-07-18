"""Point-in-time evidence materialization for generic ranking slots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import math
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash

from .candidate_ranking_contract import validate_candidate_ranking_contract


_VALUE_FIELDS = (
    "primaryEventSeverity",
    "confirmationStrength",
    "liquidity30d",
)


def _utc(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def materialize_candidate_ranking_evidence(
    *,
    signals: Sequence[Mapping[str, Any]],
    ranking_rows: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validation = validate_candidate_ranking_contract(contract)
    candidate_id = validation["candidateId"]
    rows_by_signal = {str(row.get("signalId") or ""): dict(row) for row in ranking_rows}
    records: list[dict[str, Any]] = []
    post_entry_count = 0
    available_count = 0
    for source_signal in signals:
        signal = dict(source_signal)
        signal_id = str(signal.get("signalId") or "")
        row = rows_by_signal.get(signal_id, {})
        reasons: list[str] = []
        if str(signal.get("candidateId") or "") != candidate_id:
            reasons.append("candidate_identity_mismatch")
        if not signal_id or not row:
            reasons.append("ranking_record_missing")
        if any(not _finite(row.get(field)) for field in _VALUE_FIELDS):
            reasons.append("ranking_value_missing_or_nonfinite")
        if not str(row.get("sourceHash") or ""):
            reasons.append("source_hash_missing")
        post_entry = False
        try:
            post_entry = _utc(row.get("availableAt")) > _utc(
                signal.get("expectedEntryTimestamp")
            )
        except (TypeError, ValueError):
            reasons.append("ranking_timestamp_invalid")
        if post_entry:
            post_entry_count += 1
            reasons.append("post_entry_ranking_data")
        status = "available" if not reasons else "rejected"
        if status == "available":
            available_count += 1
        record: dict[str, Any] = {
            "schemaVersion": "candidate_ranking_evidence_v1",
            "candidateId": candidate_id,
            "signalId": signal_id,
            "instrumentId": str(signal.get("instrumentId") or ""),
            "signalTimestamp": signal.get("signalTimestamp"),
            "expectedEntryTimestamp": signal.get("expectedEntryTimestamp"),
            "primaryEventSeverity": row.get("primaryEventSeverity"),
            "confirmationStrength": row.get("confirmationStrength"),
            "liquidity30d": row.get("liquidity30d"),
            "availableAt": row.get("availableAt"),
            "sourceHash": row.get("sourceHash"),
            "contractHash": validation["contractHash"],
            "rankingEvidenceStatus": status,
            "rejectionReasons": sorted(set(reasons)),
        }
        record["rankingEvidenceHash"] = stable_hash(
            record, prefix="candidate_ranking_evidence"
        )
        records.append(record)
    signal_count = len(signals)
    record_coverage = 100.0 * len(records) / signal_count if signal_count else 100.0
    availability = 100.0 * available_count / signal_count if signal_count else 100.0
    certification: dict[str, Any] = {
        "schemaVersion": "real_signal_candidate_ranking_certification_v1",
        "candidateId": candidate_id,
        "signalCount": signal_count,
        "rankingRecordCount": len(records),
        "rankingRecordCoveragePct": round(record_coverage, 6),
        "requiredRankingAvailabilityPct": round(availability, 6),
        "postEntryReadCount": post_entry_count,
        "economicReadCount": 0,
        "exitResultReadCount": 0,
        "statisticalResultReadCount": 0,
        "minimumRequiredAvailabilityPct": 95.0,
    }
    certification["status"] = (
        "passed"
        if record_coverage == 100.0
        and availability >= 95.0
        and post_entry_count == 0
        else "failed"
    )
    certification["certificationHash"] = stable_hash(
        certification, prefix="candidate_ranking_certification"
    )
    return records, certification


__all__ = ["materialize_candidate_ranking_evidence"]
