"""JSONL audit ledger skeleton."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_LEDGER_PATH = Path("reports/audit_ledger.jsonl")


@dataclass
class AuditEvent:
    event_id: str
    timestamp: str
    event_type: str
    proposal_id: str | None
    strategy_id: str | None
    symbol: str | None
    message: str
    payload: dict[str, Any] = field(default_factory=dict)


def format_audit_event(event: AuditEvent) -> str:
    return json.dumps(asdict(event), ensure_ascii=False, sort_keys=True)


def append_audit_event(
    event_type: str,
    message: str,
    proposal_id: str | None = None,
    strategy_id: str | None = None,
    symbol: str | None = None,
    payload: dict[str, Any] | None = None,
    ledger_path: Path = DEFAULT_LEDGER_PATH,
) -> AuditEvent:
    event = AuditEvent(
        event_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc).isoformat(),
        event_type=event_type,
        proposal_id=proposal_id,
        strategy_id=strategy_id,
        symbol=symbol,
        message=message,
        payload=payload or {},
    )
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as file:
        file.write(format_audit_event(event) + "\n")
    return event
