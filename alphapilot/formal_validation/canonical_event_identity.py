"""Canonical event identity shared by internal and Freqtrade projections."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash

from .candidate_adapter import CandidateAdapter, resolve_candidate_signal_identity


def _utc_iso(value: object) -> str:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        return ""
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def map_canonical_identity(
    event: Mapping[str, Any], *, adapter: CandidateAdapter, source: str
) -> dict[str, Any]:
    signal_id = resolve_candidate_signal_identity(adapter=adapter, event=event)
    exact_instrument_id = str(
        event.get("exactInstrumentId")
        or event.get("instrumentId")
        or event.get("symbol")
        or ""
    )
    signal_timestamp = _utc_iso(
        event.get("signalTimestampUtc") or event.get("signalTimestamp")
    )
    expected_entry_timestamp = _utc_iso(
        event.get("expectedEntryTimestampUtc") or event.get("entryTimestamp")
    )
    contract = {
        "candidateId": str(event.get("candidateId") or ""),
        "signalId": signal_id,
        "exactInstrumentId": exact_instrument_id,
        "direction": str(event.get("direction") or event.get("side") or ""),
        "timeframe": str(event.get("timeframe") or ""),
        "signalTimestampUtc": signal_timestamp,
        "expectedEntryTimestampUtc": expected_entry_timestamp,
        "strategyDefinitionHash": str(event.get("strategyDefinitionHash") or ""),
        "exitPolicyHash": str(event.get("exitPolicyHash") or ""),
    }
    required = (
        "candidateId",
        "signalId",
        "exactInstrumentId",
        "direction",
        "timeframe",
        "signalTimestampUtc",
        "expectedEntryTimestampUtc",
        "strategyDefinitionHash",
        "exitPolicyHash",
    )
    if any(not contract[field] for field in required):
        raise ValueError("canonical_identity_field_missing")
    return {
        **contract,
        # Compatibility aliases are excluded from the authoritative hash.
        "instrumentId": exact_instrument_id,
        "signalTimestamp": signal_timestamp,
        "entryTimestamp": expected_entry_timestamp,
        "source": str(source),
        "canonicalIdentityHash": stable_hash(contract, prefix="formal_event_identity"),
    }


def audit_canonical_identity_mapping(
    internal_events: Sequence[Mapping[str, Any]],
    freqtrade_events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [*internal_events, *freqtrade_events]
    hashes_by_id: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        hashes_by_id[str(row.get("signalId") or "")].add(
            str(row.get("canonicalIdentityHash") or "")
        )
    collision_count = sum(1 for hashes in hashes_by_id.values() if len(hashes) > 1)
    internal_ids = {str(row.get("signalId") or "") for row in internal_events}
    freqtrade_ids = {str(row.get("signalId") or "") for row in freqtrade_events}
    unmapped_internal = len(internal_ids - freqtrade_ids)
    unmapped_freqtrade = len(freqtrade_ids - internal_ids)
    denominator = max(len(internal_ids | freqtrade_ids), 1)
    matched = len(internal_ids & freqtrade_ids)
    status = (
        "certified"
        if collision_count == unmapped_internal == unmapped_freqtrade == 0
        else "blocked"
    )
    return {
        "schemaVersion": "canonical_event_identity_audit_v1",
        "status": status,
        "mappingCompletenessPct": round(100.0 * matched / denominator, 6),
        "collisionCount": collision_count,
        "unmappedInternalCount": unmapped_internal,
        "unmappedFreqtradeCount": unmapped_freqtrade,
    }
