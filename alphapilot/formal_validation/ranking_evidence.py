"""Frozen point-in-time ranking evidence with no missing-value substitution."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash


REQUIRED_RANKING_FIELDS = (
    "signalId",
    "signalTimestamp",
    "eventExtremeResidualZ",
    "recoverySizeZ",
    "liquidity30d",
    "instrumentId",
    "sourceTimestamp",
    "availableAt",
)


def _utc(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _available(value: object) -> bool:
    if value is None or value == "":
        return False
    return not isinstance(value, float) or math.isfinite(value)


def freeze_ranking_evidence(
    rows: Sequence[Mapping[str, Any]], *, ranking_policy_hash: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    frozen: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        if any(not _available(row.get(field)) for field in REQUIRED_RANKING_FIELDS):
            rejected.append({**row, "reason": "reject_ranking_field_unavailable"})
            continue
        if _utc(row["availableAt"]) > _utc(row["signalTimestamp"]):
            rejected.append({**row, "reason": "reject_post_entry_ranking_data"})
            continue
        evidence = {
            field: row[field] for field in REQUIRED_RANKING_FIELDS
        } | {"rankingPolicyHash": str(ranking_policy_hash)}
        evidence["rankingEvidenceHash"] = stable_hash(
            evidence, prefix="ranking_evidence"
        )
        frozen.append(evidence)
    return frozen, rejected


def audit_ranking_evidence_parity(
    core_rows: Sequence[Mapping[str, Any]], adapter_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    core = {str(row.get("signalId")): dict(row) for row in core_rows}
    adapter = {str(row.get("signalId")): dict(row) for row in adapter_rows}
    shared = sorted(set(core) & set(adapter))
    comparable_fields = (*REQUIRED_RANKING_FIELDS, "rankingPolicyHash")
    field_total = len(shared) * len(comparable_fields)
    field_matches = sum(
        core[key].get(field) == adapter[key].get(field)
        for key in shared
        for field in comparable_fields
    )
    hash_matches = sum(
        core[key].get("rankingEvidenceHash")
        == adapter[key].get("rankingEvidenceHash")
        for key in shared
    )
    return {
        "schemaVersion": "ranking_evidence_parity_v1",
        "fieldParityPct": round(100.0 * field_matches / field_total, 6)
        if field_total
        else 100.0,
        "hashParityPct": round(100.0 * hash_matches / len(shared), 6)
        if shared
        else 100.0,
        "postEntryDataUseCount": sum(
            _utc(row["availableAt"]) > _utc(row["signalTimestamp"])
            for row in [*core_rows, *adapter_rows]
        ),
        "unmappedCount": len(set(core) ^ set(adapter)),
    }
