"""Metadata-only identity and zero-access ledger for Future Locked OOS."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from .phase1_contracts import verify_s01_formal_preregistration


class FutureLockedOosError(RuntimeError):
    """Raised when Future Locked OOS metadata violates the frozen boundary."""


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _identity_hash_valid(identity: Mapping[str, Any]) -> bool:
    core = {key: value for key, value in identity.items() if key != "identityHash"}
    return identity.get("identityHash") == _canonical_hash(core)


def build_future_locked_oos_identity(
    *,
    candidate_id: str,
    strategy_definition_hash: str,
    formal_preregistration_hash: str,
    frozen_available_end_exclusive: str,
    future_start_inclusive: str,
    timeframe: str,
) -> dict[str, Any]:
    cutoff = _parse_utc(frozen_available_end_exclusive)
    future_start = _parse_utc(future_start_inclusive)
    if future_start <= cutoff:
        raise FutureLockedOosError(
            "Future Locked OOS must start strictly after the frozen data cutoff"
        )
    if not all(
        value.strip()
        for value in (
            candidate_id,
            strategy_definition_hash,
            formal_preregistration_hash,
            timeframe,
        )
    ):
        raise FutureLockedOosError("candidate and preregistration bindings are required")

    core: dict[str, Any] = {
        "schemaVersion": "alphapilot_future_locked_oos_identity_v1",
        "route": "future_data_required",
        "candidateId": candidate_id,
        "strategyDefinitionHash": strategy_definition_hash,
        "formalPreregistrationHash": formal_preregistration_hash,
        "timeframe": timeframe,
        "frozenAvailableEndExclusive": frozen_available_end_exclusive,
        "futureStartInclusive": future_start_inclusive,
        "futureEndExclusive": None,
        "metadataOnly": True,
        "contentHash": None,
        "dataFileCount": 0,
        "marketDataPaths": [],
        "formalWalkForwardResultHash": None,
        "accessPolicy": {
            "appendIntentBeforeContentRead": True,
            "oneShotAdmission": True,
            "contentReadAllowed": False,
        },
        "admissionStatus": "blocked",
        "blockers": [
            "future_market_data_not_available",
            "formal_walk_forward_not_completed",
        ],
    }
    return {**core, "identityHash": _canonical_hash(core)}


def _append_ledger_event(
    ledger_path: Path,
    *,
    identity_hash: str,
    event_type: str,
    access_count_delta: int,
    content_read: bool,
    purpose: str,
    attempted_path: str | None = None,
) -> dict[str, Any]:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    previous_hash: str | None = None
    if ledger_path.exists():
        lines = [
            line
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        if lines:
            previous_hash = str(json.loads(lines[-1])["eventHash"])
    core = {
        "schemaVersion": "alphapilot_future_locked_oos_ledger_event_v1",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "identityHash": identity_hash,
        "eventType": event_type,
        "purpose": purpose,
        "attemptedPath": attempted_path,
        "accessCountDelta": access_count_delta,
        "contentRead": content_read,
        "previousEventHash": previous_hash,
    }
    event = {**core, "eventHash": _canonical_hash(core)}
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def write_future_locked_oos_metadata(
    identity: Mapping[str, Any],
    *,
    identity_path: Path,
    ledger_path: Path,
    future_market_data_root: Path,
) -> dict[str, Any]:
    if not _identity_hash_valid(identity):
        raise FutureLockedOosError("Future Locked OOS identity hash is invalid")
    if Path(future_market_data_root).exists():
        raise FutureLockedOosError(
            "Future Locked OOS market-data root must not exist during metadata freeze"
        )

    if identity_path.exists():
        existing = json.loads(identity_path.read_text(encoding="utf-8"))
        if existing != dict(identity):
            raise FutureLockedOosError("existing Future Locked OOS identity differs")
    else:
        _write_json_atomic(identity_path, identity)

    if not ledger_path.exists() or not ledger_path.read_text(encoding="utf-8").strip():
        _append_ledger_event(
            ledger_path,
            identity_hash=str(identity["identityHash"]),
            event_type="identity_registered",
            access_count_delta=0,
            content_read=False,
            purpose="phase2_metadata_freeze",
        )
    return audit_future_locked_oos_metadata(identity_path, ledger_path)


def audit_future_locked_oos_metadata(
    identity_path: Path, ledger_path: Path
) -> dict[str, Any]:
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    events = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    expected_previous: str | None = None
    chain_valid = True
    for event in events:
        core = {key: value for key, value in event.items() if key != "eventHash"}
        if (
            event.get("identityHash") != identity.get("identityHash")
            or event.get("previousEventHash") != expected_previous
            or event.get("eventHash") != _canonical_hash(core)
        ):
            chain_valid = False
        expected_previous = str(event.get("eventHash"))
    access_count = sum(int(event.get("accessCountDelta") or 0) for event in events)
    content_read_count = sum(bool(event.get("contentRead")) for event in events)
    identity_valid = _identity_hash_valid(identity)
    status = (
        "passed"
        if identity_valid
        and chain_valid
        and access_count == 0
        and content_read_count == 0
        else "failed"
    )
    return {
        "schemaVersion": "alphapilot_future_locked_oos_metadata_audit_v1",
        "status": status,
        "identityHash": identity.get("identityHash"),
        "identityHashValid": identity_valid,
        "hashChainValid": chain_valid,
        "ledgerEventCount": len(events),
        "lockedOosAccessCount": access_count,
        "contentReadCount": content_read_count,
        "metadataOnly": identity.get("metadataOnly") is True,
        "contentHash": identity.get("contentHash"),
        "route": identity.get("route"),
        "admissionStatus": identity.get("admissionStatus"),
        "blockers": list(identity.get("blockers") or []),
        "lastEventHash": expected_previous,
    }


def guarded_future_locked_oos_read(
    identity_path: Path,
    ledger_path: Path,
    content_path: Path,
    *,
    purpose: str,
) -> bytes:
    """Record access intent before any future content can be opened."""

    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    if not _identity_hash_valid(identity):
        raise FutureLockedOosError("Future Locked OOS identity hash is invalid")
    _append_ledger_event(
        ledger_path,
        identity_hash=str(identity["identityHash"]),
        event_type="access_intent_denied",
        access_count_delta=1,
        content_read=False,
        purpose=purpose,
        attempted_path=str(Path(content_path).absolute()),
    )
    if identity.get("route") != "locked_oos_ready":
        raise FutureLockedOosError("Future Locked OOS future data is unavailable")
    raise FutureLockedOosError("Future Locked OOS content access is not enabled")


def write_phase2_future_locked_oos_evidence(
    repo_root: Path,
    evidence_root: Path,
    *,
    metadata_root: Path | None = None,
) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve(strict=True)
    evidence_root = Path(evidence_root).resolve(strict=False)
    preregistration_path = (
        repo_root
        / "research"
        / "preregistrations"
        / "advisory_r_v17_s01_formal_walk_forward.json"
    )
    preregistration = json.loads(preregistration_path.read_text(encoding="utf-8"))
    if not verify_s01_formal_preregistration(preregistration):
        raise FutureLockedOosError("formal S01 preregistration hash is invalid")

    split = preregistration["splitPolicy"]
    cutoff_text = str(split["commonCutoffExclusive"])
    bar_hours = int(split["barHours"])
    future_start = _parse_utc(cutoff_text) + timedelta(hours=bar_hours)
    future_start_text = future_start.isoformat().replace("+00:00", "Z")
    identity = build_future_locked_oos_identity(
        candidate_id=str(preregistration["sourceCandidateId"]),
        strategy_definition_hash=str(preregistration["strategyDefinitionHash"]),
        formal_preregistration_hash=str(preregistration["preregistrationHash"]),
        frozen_available_end_exclusive=cutoff_text,
        future_start_inclusive=future_start_text,
        timeframe=str(split["timeframe"]),
    )

    metadata_root = (
        Path(metadata_root).resolve(strict=False)
        if metadata_root is not None
        else repo_root / "research" / "locked_oos"
    )
    identity_path = metadata_root / "s01_future_locked_oos_identity.json"
    ledger_path = metadata_root / "s01_future_locked_oos_access_ledger.jsonl"
    future_market_data_root = metadata_root / "future_market_data"
    audit = write_future_locked_oos_metadata(
        identity,
        identity_path=identity_path,
        ledger_path=ledger_path,
        future_market_data_root=future_market_data_root,
    )
    def display_path(path: Path) -> str:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return str(path)

    readiness = {
        "schemaVersion": "alphapilot_future_locked_oos_readiness_v1",
        "status": "passed" if audit["status"] == "passed" else "failed",
        "identityPath": display_path(identity_path),
        "ledgerPath": display_path(ledger_path),
        "futureMarketDataRoot": display_path(future_market_data_root),
        "identityHash": identity["identityHash"],
        "candidateId": identity["candidateId"],
        "formalPreregistrationHash": identity["formalPreregistrationHash"],
        "strategyDefinitionHash": identity["strategyDefinitionHash"],
        "route": identity["route"],
        "admissionStatus": "blocked",
        "blockers": identity["blockers"],
        "audit": audit,
        "formalResultCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    _write_json_atomic(
        evidence_root / "future_locked_oos_readiness.json", readiness
    )
    return readiness
