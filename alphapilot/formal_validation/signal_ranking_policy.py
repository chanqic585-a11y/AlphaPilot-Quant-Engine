"""Deterministic same-timestamp signal ranking for V18."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash


RANKING_POLICY_V1: dict[str, Any] = {
    "schemaVersion": "s01_signal_ranking_policy_v1",
    "batchDefinition": "same_expected_entry_timestamp",
    "fields": [
        {"name": "eventExtremeResidualZ", "order": "ascending"},
        {"name": "recoverySizeZ", "order": "descending"},
        {"name": "liquidity30d", "order": "descending"},
        {"name": "instrumentId", "order": "ascending"},
    ],
    "missingDataPolicy": "reject_if_any_of_first_three_fields_missing_or_nonfinite",
    "mixedTimestampPolicy": "reject_entire_batch",
    "duplicateInstrumentPolicy": "reject_duplicate_rows",
    "tiePolicy": "instrument_id_is_final_tiebreak_and_must_be_unique",
}
RANKING_POLICY_V1["definitionHash"] = stable_hash(
    RANKING_POLICY_V1, prefix="s01_signal_ranking_policy_v1"
)


def _utc_text(value: object) -> str:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def rank_signal_batch_v1(
    signals: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [dict(row) for row in signals]
    if not rows:
        return {
            "ranked": [],
            "rejected": [],
            "rankingPolicyHash": RANKING_POLICY_V1["definitionHash"],
        }
    try:
        timestamps = {_utc_text(row.get("entryTimestamp")) for row in rows}
    except (TypeError, ValueError):
        timestamps = set()
    if len(timestamps) != 1:
        return {
            "ranked": [],
            "rejected": [{**row, "reason": "mixed_entry_timestamp"} for row in rows],
            "rankingPolicyHash": RANKING_POLICY_V1["definitionHash"],
        }

    valid: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        instrument = str(row.get("instrumentId") or "")
        values = (
            _finite(row.get("eventExtremeResidualZ")),
            _finite(row.get("recoverySizeZ")),
            _finite(row.get("liquidity30d")),
        )
        if not instrument or any(value is None for value in values):
            rejected.append({**row, "reason": "missing_ranking_field"})
            continue
        if instrument in seen:
            rejected.append({**row, "reason": "duplicate_instrument_in_batch"})
            continue
        seen.add(instrument)
        valid.append(
            {
                **row,
                "entryTimestamp": next(iter(timestamps)),
                "eventExtremeResidualZ": values[0],
                "recoverySizeZ": values[1],
                "liquidity30d": values[2],
            }
        )
    ranked = sorted(
        valid,
        key=lambda row: (
            row["eventExtremeResidualZ"],
            -row["recoverySizeZ"],
            -row["liquidity30d"],
            str(row["instrumentId"]),
        ),
    )
    return {
        "ranked": ranked,
        "rejected": rejected,
        "entryTimestamp": next(iter(timestamps)),
        "rankingPolicyHash": RANKING_POLICY_V1["definitionHash"],
    }
