"""Append-only, hash-chained evidence ledger for automatic research programs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


class ProgramLedger:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        records: list[dict[str, Any]] = []
        previous_hash: str | None = None
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            record = json.loads(line)
            supplied_hash = record.get("recordHash")
            canonical_record = {key: value for key, value in record.items() if key != "recordHash"}
            if supplied_hash != stable_hash(canonical_record):
                raise ValueError(f"ledger record hash mismatch at line {line_number}")
            if record.get("previousRecordHash") != previous_hash:
                raise ValueError(f"ledger hash chain mismatch at line {line_number}")
            if record.get("sequence") != len(records) + 1:
                raise ValueError(f"ledger sequence mismatch at line {line_number}")
            records.append(record)
            previous_hash = str(supplied_hash)
        return records

    def append(
        self,
        *,
        event_type: str,
        stage: str,
        created_at: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        event_identity = {
            "eventType": event_type,
            "stage": stage,
            "createdAt": created_at,
            "payload": payload,
        }
        event_id = stable_hash(event_identity, prefix="program_event")
        records = self.read_all()
        for record in records:
            if record.get("eventId") == event_id:
                return record

        record: dict[str, Any] = {
            "schemaVersion": "automatic_strategy_demo_program_ledger_v1",
            "sequence": len(records) + 1,
            "eventId": event_id,
            "eventType": event_type,
            "stage": stage,
            "createdAt": created_at,
            "payload": payload,
            "previousRecordHash": records[-1]["recordHash"] if records else None,
        }
        record["recordHash"] = stable_hash(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return record
