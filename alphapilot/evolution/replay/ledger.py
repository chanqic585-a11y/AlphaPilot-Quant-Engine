"""Persist replay outcomes as immutable registry rows and a hashed artifact."""

from __future__ import annotations

import os
from dataclasses import fields
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import OutcomeLedgerRecord

from .types import ReplayResult, ReplayTrade


def _iso(timestamp_ms: int) -> str:
    return pd.Timestamp(timestamp_ms, unit="ms", tz="UTC").isoformat()


def persist_replay_outcomes(
    result: ReplayResult,
    *,
    repository: RegistryRepository,
    data_snapshot_id: str,
    source_entity_type: str,
    source_entity_id: str,
    evidence_class: str,
    code_commit: str | None = None,
    output_root: Path | str = "data/market/replay",
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    outcome_ids: list[str] = []
    for trade in result.trades:
        payload = {
            "schemaVersion": "historical_replay_outcome_v1",
            "evidenceClass": evidence_class,
            "trade": trade.to_dict(),
            "usesActualCanonicalCandlePath": True,
            "nextBarFill": True,
            "researchOnly": True,
            "createsOrders": False,
            "codeCommit": code_commit,
        }
        outcome_id = stable_hash(
            {
                "dataSnapshotId": data_snapshot_id,
                "sourceEntityType": source_entity_type,
                "sourceEntityId": source_entity_id,
                "signalId": trade.signalId,
                "payload": payload,
            },
            prefix="outcome",
        )
        repository.create_outcome(
            OutcomeLedgerRecord(
                outcomeId=outcome_id,
                evidenceClass=evidence_class,
                sourceEntityType=source_entity_type,
                sourceEntityId=source_entity_id,
                dataSnapshotId=data_snapshot_id,
                strategyCandidateId=trade.strategyCandidateId,
                instrumentId=trade.instrumentId,
                timeframe=trade.timeframe,
                direction=trade.direction,
                decisionAt=_iso(trade.decisionTimestampMs),
                entryAt=_iso(trade.entryTimestampMs),
                exitAt=_iso(trade.exitTimestampMs),
                status="closed",
                outcome=payload,
                contentHash=stable_hash(payload),
            )
        )
        rows.append({"outcomeId": outcome_id, **trade.to_dict()})
        outcome_ids.append(outcome_id)
    output_directory = Path(output_root).resolve() / source_entity_id
    output_directory.mkdir(parents=True, exist_ok=True)
    artifact_path = output_directory / "outcomes.parquet"
    temporary = artifact_path.with_name(f"{artifact_path.name}.tmp")
    artifact_columns = ["outcomeId", *(field.name for field in fields(ReplayTrade))]
    pd.DataFrame(rows, columns=artifact_columns).to_parquet(
        temporary, index=False, compression="zstd"
    )
    os.replace(temporary, artifact_path)
    artifact_sha = sha256_file(artifact_path)
    manifest = {
        "schemaVersion": "historical_replay_outcome_manifest_v1",
        "dataSnapshotId": data_snapshot_id,
        "sourceEntityType": source_entity_type,
        "sourceEntityId": source_entity_id,
        "evidenceClass": evidence_class,
        "codeCommit": code_commit,
        "outcomeCount": len(rows),
        "outcomeIds": outcome_ids,
        "artifactPath": str(artifact_path),
        "artifactSha256": artifact_sha,
        "formalPromotionEligible": False,
        "createsOrders": False,
    }
    write_json_atomic(output_directory / "manifest.json", manifest)
    return manifest
