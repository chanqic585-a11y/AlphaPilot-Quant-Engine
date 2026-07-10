"""Import checksum-bound closed Demo/Live outcomes into the offline ledger."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import OutcomeLedgerRecord


EXPORT_SCHEMA_VERSION = "alphapilot_execution_outcome_export_v1"
OUTCOME_SCHEMA_VERSION = "alphapilot_execution_outcome_v1"
FORMAL_EXECUTION_CLASSES = {"okx_demo", "live"}
SENSITIVE_KEY_FRAGMENTS = (
    "apikey",
    "secretkey",
    "passphrase",
    "accountbalance",
    "cashbalance",
    "totaleq",
    "availbal",
)


@dataclass(frozen=True)
class ExecutionOutcomeImportResult:
    status: str
    sourcePath: str
    manifestHash: str
    recordCount: int
    importedCount: int
    duplicateCount: int
    importedOutcomeIds: list[str]
    quarantined: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "sourcePath": self.sourcePath,
            "manifestHash": self.manifestHash,
            "recordCount": self.recordCount,
            "importedCount": self.importedCount,
            "duplicateCount": self.duplicateCount,
            "importedOutcomeIds": self.importedOutcomeIds,
            "quarantinedCount": len(self.quarantined),
            "quarantined": self.quarantined,
            "inventedLineage": False,
            "accountValuesImported": False,
        }


def _parse_time(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("event_time_timezone_missing")
    return parsed


def _finite_number(value: Any, key: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"trade_number_invalid:{key}") from error
    if not math.isfinite(number):
        raise ValueError(f"trade_number_invalid:{key}")
    return number


def _has_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).replace("_", "").lower()
            if any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS):
                return True
            if _has_sensitive_key(item):
                return True
    elif isinstance(value, list):
        return any(_has_sensitive_key(item) for item in value)
    return False


def _validate_export(payload: Any) -> tuple[list[dict[str, Any]], str]:
    if not isinstance(payload, dict) or payload.get("schemaVersion") != EXPORT_SCHEMA_VERSION:
        raise ValueError("execution_outcome_export_schema_invalid")
    records = payload.get("records")
    quarantined = payload.get("quarantinedExecutionRecords")
    if not isinstance(records, list) or not isinstance(quarantined, list):
        raise ValueError("execution_outcome_export_shape_invalid")
    core = {
        "schemaVersion": payload["schemaVersion"],
        "records": records,
        "quarantinedExecutionRecords": quarantined,
    }
    expected = stable_hash(core)
    manifest_hash = str(payload.get("manifestHash") or "")
    if not manifest_hash or manifest_hash != expected:
        raise ValueError("execution_outcome_export_manifest_mismatch")
    if _has_sensitive_key(payload):
        raise ValueError("execution_outcome_export_contains_private_values")
    return records, manifest_hash


def _validate_record_hash(record: dict[str, Any]) -> None:
    base = {
        key: value
        for key, value in record.items()
        if key not in {"executionOutcomeId", "contentHash", "createdAt"}
    }
    if str(record.get("contentHash") or "") != stable_hash(base):
        raise ValueError("execution_outcome_content_hash_mismatch")


def _validate_trade(record: dict[str, Any]) -> dict[str, Any]:
    trade = record.get("trade")
    if not isinstance(trade, dict):
        raise ValueError("trade_payload_missing")
    numbers = {
        key: _finite_number(trade.get(key), key)
        for key in (
            "entryPrice",
            "exitPrice",
            "quantity",
            "grossPnl",
            "feePaid",
            "slippagePaid",
            "netPnl",
            "riskAmount",
            "grossR",
            "netR",
        )
    }
    if any(numbers[key] <= 0 for key in ("entryPrice", "exitPrice", "quantity", "riskAmount")):
        raise ValueError("trade_positive_value_required")
    if numbers["feePaid"] < 0 or numbers["slippagePaid"] < 0:
        raise ValueError("trade_cost_negative")
    expected_net = numbers["grossPnl"] - numbers["feePaid"] - numbers["slippagePaid"]
    pnl_tolerance = max(1e-8, abs(expected_net) * 1e-8)
    if abs(expected_net - numbers["netPnl"]) > pnl_tolerance:
        raise ValueError("trade_net_pnl_mismatch")
    gross_r = numbers["grossPnl"] / numbers["riskAmount"]
    net_r = numbers["netPnl"] / numbers["riskAmount"]
    if abs(numbers["grossR"] - gross_r) > max(1e-8, abs(gross_r) * 1e-8):
        raise ValueError("trade_gross_r_mismatch")
    if abs(numbers["netR"] - net_r) > max(1e-8, abs(net_r) * 1e-8):
        raise ValueError("trade_net_r_mismatch")
    if trade.get("sameBarAmbiguous") is not False:
        raise ValueError("trade_path_ambiguous")
    if not str(trade.get("exitReason") or "").strip():
        raise ValueError("trade_exit_reason_missing")
    return {**trade, **numbers}


def _validated_lineage(
    record: dict[str, Any],
    repository: RegistryRepository,
) -> tuple[str, str]:
    evidence_class = str(record.get("evidenceClass") or "")
    release_id = str(record.get("releaseId") or "")
    release_hash = str(record.get("releaseHash") or "")
    candidate_id = str(record.get("strategyCandidateId") or "")
    snapshot_id = str(record.get("dataSnapshotId") or "")
    if repository.get_data_snapshot(snapshot_id) is None:
        raise ValueError("data_snapshot_missing")
    if repository.get_strategy_candidate(candidate_id) is None:
        raise ValueError("strategy_candidate_missing")
    if evidence_class == "okx_demo":
        release = repository.get_demo_release(release_id)
        if release is None:
            raise ValueError("demo_release_missing")
        if release.contentHash != release_hash:
            raise ValueError("demo_release_hash_mismatch")
        if release.strategyCandidateId != candidate_id:
            raise ValueError("demo_release_candidate_mismatch")
        return "demoReleaseId", release_id
    release = repository.get_live_release(release_id)
    if release is None:
        raise ValueError("live_release_missing")
    if release.contentHash != release_hash:
        raise ValueError("live_release_hash_mismatch")
    if release.strategyCandidateId != candidate_id:
        raise ValueError("live_release_candidate_mismatch")
    risk_profile_id = str(record.get("riskProfileId") or "")
    risk_profile_hash = str(record.get("riskProfileHash") or "")
    if release.riskProfileId != risk_profile_id:
        raise ValueError("live_release_risk_profile_mismatch")
    risk_profile = repository.get_risk_profile(risk_profile_id)
    if risk_profile is None:
        raise ValueError("risk_profile_missing")
    if risk_profile.contentHash != risk_profile_hash:
        raise ValueError("risk_profile_hash_mismatch")
    return "liveReleaseId", release_id


def _build_ledger_record(
    record: dict[str, Any],
    repository: RegistryRepository,
) -> OutcomeLedgerRecord:
    if record.get("schemaVersion") != OUTCOME_SCHEMA_VERSION:
        raise ValueError("execution_outcome_schema_invalid")
    evidence_class = str(record.get("evidenceClass") or "")
    if evidence_class not in FORMAL_EXECUTION_CLASSES:
        raise ValueError("execution_evidence_class_invalid")
    if record.get("environment") != evidence_class:
        raise ValueError("execution_environment_mismatch")
    if record.get("status") != "closed":
        raise ValueError("execution_outcome_not_closed")
    if record.get("accountValuesPersisted") is not False:
        raise ValueError("execution_outcome_account_values_present")
    if _has_sensitive_key(record):
        raise ValueError("execution_outcome_contains_private_values")
    expected_entity_type = "okx_demo_execution" if evidence_class == "okx_demo" else "okx_live_execution"
    if record.get("sourceEntityType") != expected_entity_type:
        raise ValueError("execution_source_entity_type_invalid")
    if str(record.get("direction") or "") not in {"long", "short"}:
        raise ValueError("execution_direction_invalid")
    required_text = (
        "executionOutcomeId",
        "sourceEntityId",
        "releaseId",
        "releaseHash",
        "strategyCandidateId",
        "dataSnapshotId",
        "instrumentId",
        "timeframe",
        "decisionAt",
        "entryAt",
        "exitAt",
        "sourcePayloadHash",
        "contentHash",
    )
    missing = [key for key in required_text if not str(record.get(key) or "").strip()]
    if missing:
        raise ValueError("execution_source_lineage_missing:" + ",".join(missing))
    _validate_record_hash(record)
    decision_at = _parse_time(record.get("decisionAt"))
    entry_at = _parse_time(record.get("entryAt"))
    exit_at = _parse_time(record.get("exitAt"))
    if not decision_at <= entry_at <= exit_at:
        raise ValueError("event_time_order_invalid")
    trade = _validate_trade(record)
    release_key, release_id = _validated_lineage(record, repository)
    source_entity_id = str(record.get("sourceEntityId") or "")
    source_payload_hash = str(record.get("sourcePayloadHash") or "")
    external_id = str(record.get("executionOutcomeId") or "")
    external_hash = str(record.get("contentHash") or "")
    if not source_entity_id or not source_payload_hash or not external_id or not external_hash:
        raise ValueError("execution_source_lineage_missing")
    outcome = {
        "schemaVersion": "alphapilot_imported_execution_outcome_v1",
        "evidenceClass": evidence_class,
        release_key: release_id,
        "releaseHash": str(record["releaseHash"]),
        "riskProfileId": str(record.get("riskProfileId") or ""),
        "riskProfileHash": str(record.get("riskProfileHash") or ""),
        "trade": trade,
        "sourcePayloadHash": source_payload_hash,
        "externalExecutionOutcomeId": external_id,
        "externalContentHash": external_hash,
        "accountValuesPersisted": False,
    }
    identity = {
        "evidenceClass": evidence_class,
        "sourceEntityType": record["sourceEntityType"],
        "sourceEntityId": source_entity_id,
        "externalContentHash": external_hash,
    }
    return OutcomeLedgerRecord(
        outcomeId=stable_hash(identity, prefix="formal_execution_outcome"),
        evidenceClass=evidence_class,
        sourceEntityType=str(record["sourceEntityType"]),
        sourceEntityId=source_entity_id,
        dataSnapshotId=str(record["dataSnapshotId"]),
        strategyCandidateId=str(record["strategyCandidateId"]),
        instrumentId=str(record["instrumentId"]),
        timeframe=str(record["timeframe"]),
        direction=str(record["direction"]),
        decisionAt=str(record["decisionAt"]),
        entryAt=str(record["entryAt"]),
        exitAt=str(record["exitAt"]),
        status="closed",
        outcome=outcome,
        contentHash=stable_hash(outcome),
        createdAt=str(record.get("createdAt") or record["exitAt"]),
    )


def import_execution_outcome_export(
    source_path: str | Path,
    *,
    repository: RegistryRepository,
) -> ExecutionOutcomeImportResult:
    path = Path(source_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    records, manifest_hash = _validate_export(payload)
    imported: list[str] = []
    duplicate_count = 0
    quarantined: list[dict[str, str]] = []
    for index, raw in enumerate(records):
        if not isinstance(raw, dict):
            quarantined.append({"record": str(index), "reason": "execution_outcome_record_invalid"})
            continue
        external_id = str(raw.get("executionOutcomeId") or index)
        try:
            ledger_record = _build_ledger_record(raw, repository)
            existing = repository.get_outcome(ledger_record.outcomeId)
            if existing is not None:
                if existing.contentHash != ledger_record.contentHash:
                    raise ValueError("execution_outcome_registry_conflict")
                duplicate_count += 1
                continue
            repository.create_outcome(ledger_record)
            imported.append(ledger_record.outcomeId)
        except (KeyError, TypeError, ValueError) as error:
            quarantined.append({"record": external_id, "reason": str(error)})
    status = "completed" if records else "blocked_no_formal_execution_outcomes"
    if records and not imported and duplicate_count == 0:
        status = "blocked_all_execution_outcomes_quarantined"
    return ExecutionOutcomeImportResult(
        status=status,
        sourcePath=str(path.resolve()),
        manifestHash=manifest_hash,
        recordCount=len(records),
        importedCount=len(imported),
        duplicateCount=duplicate_count,
        importedOutcomeIds=imported,
        quarantined=quarantined,
    )
