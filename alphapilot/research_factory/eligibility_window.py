"""Causal eligibility-window and event-disposition contracts for V28."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash


EVENT_DISPOSITIONS = (
    "eligible_candidate_event",
    "excluded_before_capacity_history_ready",
    "excluded_after_common_cutoff",
    "excluded_missing_verified_semantics",
    "excluded_instrument_not_in_frozen_universe",
)


def _timestamp(value: object, *, field: str) -> pd.Timestamp:
    parsed = pd.Timestamp(str(value))
    if pd.isna(parsed):
        raise ValueError(f"invalid_timestamp:{field}")
    if parsed.tzinfo is None:
        return parsed.tz_localize("UTC")
    return parsed.tz_convert("UTC")


def build_causal_eligibility_window(
    *,
    instrument_id: str,
    timeframe: str,
    data_profile_id: str,
    candle_timestamps: Sequence[str],
    field_specs: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Freeze the first causal signal timestamp before candidate creation."""

    candles = sorted({_timestamp(value, field="candle") for value in candle_timestamps})
    if not instrument_id or not timeframe or not data_profile_id or not candles:
        raise ValueError("eligibility_window_identity_or_candles_missing")
    if not field_specs:
        raise ValueError("eligibility_window_fields_missing")

    field_rows: list[dict[str, Any]] = []
    eligible_indexes: list[int] = []
    for field_name, raw_spec in sorted(field_specs.items()):
        first_available = _timestamp(
            raw_spec.get("fieldFirstAvailableAt"), field=f"{field_name}.firstAvailableAt"
        )
        lookback = int(raw_spec.get("requiredLookbackBars") or 0)
        semantics_verified = raw_spec.get("semanticsVerified") is True
        available_at_rule = str(raw_spec.get("availableAtRule") or "")
        if lookback < 1:
            raise ValueError(f"invalid_required_lookback:{field_name}")
        if not semantics_verified or not available_at_rule:
            raise ValueError(f"unverified_field_semantics:{field_name}")
        first_index = next(
            (index for index, candle in enumerate(candles) if candle >= first_available),
            None,
        )
        if first_index is None or first_index + lookback - 1 >= len(candles):
            raise ValueError(f"insufficient_field_history:{field_name}")
        eligible_index = first_index + lookback - 1
        eligible_indexes.append(eligible_index)
        field_rows.append(
            {
                "field": str(field_name),
                "fieldFirstAvailableAt": first_available.isoformat(),
                "requiredLookbackBars": lookback,
                "firstEligibleSignalTimestamp": candles[eligible_index].isoformat(),
                "semanticsVerified": True,
                "availableAtRule": available_at_rule,
            }
        )

    payload: dict[str, Any] = {
        "schemaVersion": "causal_eligibility_window_v1",
        "instrumentId": str(instrument_id),
        "timeframe": str(timeframe),
        "dataProfileId": str(data_profile_id),
        "fields": field_rows,
        "firstEligibleSignalTimestamp": candles[max(eligible_indexes)].isoformat(),
        "lastEligibleSignalTimestamp": candles[-1].isoformat(),
        "createdBeforeCandidateIdentity": True,
    }
    payload["windowHash"] = stable_hash(payload, prefix="causal_eligibility_window")
    return payload


def classify_event_dispositions(
    *,
    raw_events: Sequence[Mapping[str, Any]],
    eligibility_windows: Mapping[str, Mapping[str, Any]],
    frozen_universe: Iterable[str],
    common_cutoff: str,
) -> dict[str, Any]:
    """Classify every raw event exactly once and fail on causal leakage."""

    universe = {str(value) for value in frozen_universe if str(value)}
    cutoff = _timestamp(common_cutoff, field="commonCutoff")
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    post_entry_reads = 0
    eligible_capacity_complete = 0

    for raw in raw_events:
        event = dict(raw)
        instrument = str(event.get("instrumentId") or "")
        signal_at = _timestamp(event.get("signalTimestamp"), field="signalTimestamp")
        entry_at = _timestamp(event.get("entryTimestamp"), field="entryTimestamp")
        max_read_at = _timestamp(
            event.get("dataReadMaxTimestamp"), field="dataReadMaxTimestamp"
        )
        if max_read_at > entry_at:
            post_entry_reads += 1
            raise ValueError(f"post_entry_data_read:{event.get('eventId') or ''}")

        window = eligibility_windows.get(instrument)
        if instrument not in universe or window is None:
            disposition = "excluded_instrument_not_in_frozen_universe"
        elif signal_at > cutoff:
            disposition = "excluded_after_common_cutoff"
        elif event.get("semanticsVerified") is not True:
            disposition = "excluded_missing_verified_semantics"
        else:
            first_eligible = _timestamp(
                window.get("firstEligibleSignalTimestamp"), field="firstEligibleSignalTimestamp"
            )
            last_eligible = _timestamp(
                window.get("lastEligibleSignalTimestamp"), field="lastEligibleSignalTimestamp"
            )
            if signal_at < first_eligible or signal_at > last_eligible:
                disposition = "excluded_before_capacity_history_ready"
            else:
                disposition = "eligible_candidate_event"
                eligible_capacity_complete += int(
                    event.get("capacityInputsComplete") is True
                )
        counts[disposition] += 1
        rows.append(
            {
                "eventId": str(event.get("eventId") or ""),
                "instrumentId": instrument,
                "signalTimestamp": signal_at.isoformat(),
                "entryTimestamp": entry_at.isoformat(),
                "dataReadMaxTimestamp": max_read_at.isoformat(),
                "disposition": disposition,
            }
        )

    eligible_count = counts["eligible_candidate_event"]
    capacity_coverage = (
        100.0 if eligible_count == 0 else 100.0 * eligible_capacity_complete / eligible_count
    )
    if capacity_coverage != 100.0:
        raise ValueError("eligible_capacity_coverage_incomplete")
    disposition_counts = {name: int(counts[name]) for name in EVENT_DISPOSITIONS}
    raw_count = len(raw_events)
    classified_count = sum(disposition_counts.values())
    payload: dict[str, Any] = {
        "schemaVersion": "causal_event_disposition_audit_v1",
        "commonCutoff": cutoff.isoformat(),
        "rawSignalCount": raw_count,
        "eligibleCandidateEventCount": eligible_count,
        "dispositionCounts": disposition_counts,
        "eventConservationPassed": raw_count == classified_count,
        "eligibleCapacityCoveragePct": round(capacity_coverage, 6),
        "unclassifiedEventCount": raw_count - classified_count,
        "postEntryReadCount": post_entry_reads,
        "events": rows,
    }
    if not payload["eventConservationPassed"]:
        raise ValueError("event_disposition_conservation_failed")
    payload["auditHash"] = stable_hash(payload, prefix="causal_event_disposition")
    return payload

