from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from .candidate_deduplication import deduplicate_candidates
from .candidate_selection import discover_candidates
from .hashing import stable_hash
from .models import CandidateDeduplicationReport, CandidateVersion
from .signal_freezer import SignalDefinitionUnreproducible, freeze_signal_definition


def _json_object(value: str | None) -> dict[str, Any]:
    parsed = json.loads(value or "{}")
    return parsed if isinstance(parsed, dict) else {}


def _read_only_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def load_candidate_preregistration_records(
    *,
    failure_attributions: Iterable[dict[str, Any]],
    registry_path: Path,
) -> tuple[list[dict[str, Any]], CandidateDeduplicationReport, dict[str, Any]]:
    discovered = discover_candidates(failure_attributions)
    if not discovered:
        return [], deduplicate_candidates([]), {"unreproducible": {}}

    ids = [candidate.strategy_version_id for candidate in discovered]
    placeholders = ",".join("?" for _ in ids)
    connection = _read_only_connection(registry_path)
    try:
        strategy_rows = {
            row["strategyVersionId"]: row
            for row in connection.execute(
                f"SELECT * FROM StrategyVersions WHERE strategyVersionId IN ({placeholders})",
                ids,
            )
        }
        enriched: list[CandidateVersion] = []
        frozen_by_id: dict[str, Any] = {}
        unreproducible: dict[str, str] = {}
        for candidate in discovered:
            row = strategy_rows.get(candidate.strategy_version_id)
            if row is None:
                unreproducible[candidate.strategy_version_id] = "strategy_registry_row_missing"
                enriched.append(candidate)
                continue
            definition = _json_object(row["definitionJson"])
            try:
                frozen = freeze_signal_definition(candidate.strategy_version_id, definition)
            except SignalDefinitionUnreproducible as exc:
                unreproducible[candidate.strategy_version_id] = str(exc)
                enriched.append(
                    replace(
                        candidate,
                        source_definition_hash=str(row["contentHash"] or "") or None,
                    )
                )
                continue
            frozen_by_id[candidate.strategy_version_id] = frozen
            enriched.append(
                replace(
                    candidate,
                    source_definition_hash=frozen.strategy_definition_hash,
                    source_signal_hash=frozen.signal_definition_hash,
                    parent_strategy_version_id=(
                        str(row["parentStrategyVersionId"])
                        if row["parentStrategyVersionId"]
                        else None
                    ),
                )
            )

        deduplication = deduplicate_candidates(enriched)
        records: list[dict[str, Any]] = []
        for representative in deduplication.canonical_candidates:
            version_id = representative.strategy_version_id
            row = strategy_rows.get(version_id)
            frozen = frozen_by_id.get(version_id)
            definition = _json_object(row["definitionJson"]) if row else {}
            binding_row = connection.execute(
                """
                SELECT e.*, w.createdAt AS workflowCreatedAt
                FROM EvaluationBindings e
                JOIN WorkflowRuns w ON w.workflowRunId = e.workflowRunId
                WHERE w.strategyVersionId = ?
                ORDER BY w.createdAt DESC, e.createdAt DESC
                LIMIT 1
                """,
                (version_id,),
            ).fetchone()
            snapshot_row = None
            contract_row = None
            if binding_row is not None:
                snapshot_row = connection.execute(
                    "SELECT * FROM DataSnapshots WHERE dataSnapshotId = ?",
                    (binding_row["dataSnapshotId"],),
                ).fetchone()
                contract_row = connection.execute(
                    "SELECT * FROM StrategyDataContracts WHERE strategyDataContractId = ?",
                    (binding_row["strategyDataContractId"],),
                ).fetchone()
            contract = _json_object(contract_row["contractJson"]) if contract_row else {}
            universe_policy = contract.get("universePolicy") or definition.get(
                "universePolicy"
            )
            historical_point_in_time = (
                universe_policy.get("historicalPointInTime")
                if isinstance(universe_policy, dict)
                else None
            )
            split_hashes = (
                {
                    "walkForwardManifestHash": binding_row["walkForwardManifestHash"],
                    "holdoutManifestHash": binding_row["holdoutManifestHash"],
                    "lockedOosManifestHash": binding_row["lockedOosManifestHash"],
                }
                if binding_row is not None
                else {
                    "walkForwardManifestHash": None,
                    "holdoutManifestHash": None,
                    "lockedOosManifestHash": None,
                }
            )
            duplicate_ids = sorted(
                candidate.strategy_version_id
                for candidate in enriched
                if deduplication.version_to_representative.get(
                    candidate.strategy_version_id
                )
                == version_id
            )
            record = {
                "strategyVersionId": version_id,
                "duplicateStrategyVersionIds": duplicate_ids,
                "strategyFamily": representative.strategy_family,
                "strategyFamilyId": row["strategyFamilyId"] if row else None,
                "displayLabelZh": representative.display_label_zh,
                "tier": representative.tier,
                "timeframe": representative.timeframe,
                "direction": definition.get("direction"),
                "signalFrozen": frozen is not None,
                "signalDefinitionHash": (
                    frozen.signal_definition_hash if frozen is not None else None
                ),
                "strategyDefinitionHash": (
                    frozen.strategy_definition_hash if frozen is not None else None
                ),
                "dataSnapshotId": (
                    snapshot_row["dataSnapshotId"] if snapshot_row else None
                ),
                "dataSnapshotHash": (
                    snapshot_row["contentHash"] if snapshot_row else None
                ),
                "dataStartTime": snapshot_row["startTime"] if snapshot_row else None,
                "dataEndTime": snapshot_row["endTime"] if snapshot_row else None,
                "pointInTimeCutoff": (
                    snapshot_row["pointInTimeCutoff"] if snapshot_row else None
                ),
                **split_hashes,
                "splitManifestHash": stable_hash(split_hashes),
                "universePolicy": universe_policy,
                "historicalPointInTimeUniverse": historical_point_in_time,
                "survivorshipAuditStatus": (
                    "registered_point_in_time"
                    if historical_point_in_time is True
                    else "unavailable_current_snapshot_universe"
                ),
                "historicalPrefilter": {
                    "required": representative.requires_prefilter,
                    "passed": representative.historical_prefilter_passed,
                    "profitFactor": representative.historical_profit_factor,
                    "averageNetR": representative.historical_average_net_r,
                    "tradeCount": representative.historical_trade_count,
                },
                "signalUnreproducibleReason": unreproducible.get(version_id),
            }
            identity = {
                key: record.get(key)
                for key in (
                    "strategyVersionId",
                    "signalDefinitionHash",
                    "timeframe",
                    "dataSnapshotHash",
                    "splitManifestHash",
                )
            }
            record["validationIdentityHash"] = stable_hash(identity)
            records.append(record)
        return records, deduplication, {"unreproducible": unreproducible}
    finally:
        connection.close()
