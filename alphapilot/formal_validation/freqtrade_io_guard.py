"""Physical path and access-log guard for later formal Freqtrade execution."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


class FreqtradeIOGuardError(RuntimeError):
    """Raised when a formal data read is outside the immutable I/O contract."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _overlap(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _contains_symlink(path: Path, *, stop_at: Path | None = None) -> bool:
    absolute = path.absolute()
    stop = stop_at.absolute() if stop_at is not None else None
    current = absolute
    while True:
        if current.is_symlink():
            return True
        if stop is not None and current == stop:
            return False
        parent = current.parent
        if parent == current:
            return False
        current = parent


def build_freqtrade_io_contract(
    *,
    input_root: Path,
    allowed_files: Sequence[Path],
    output_root: Path,
    requested_start: str,
    requested_end: str,
    allowed_start: str,
    allowed_end: str,
    forbidden_roots: Sequence[Path],
    runtime_image: str,
    runtime_command: Sequence[str],
) -> dict[str, Any]:
    input_path = Path(input_root).resolve(strict=True)
    output_path = Path(output_root).resolve(strict=False)
    forbidden = sorted(
        {str(Path(root).resolve(strict=False)) for root in forbidden_roots}
    )
    forbidden_paths = [Path(value) for value in forbidden]
    if (requested_start, requested_end) != (allowed_start, allowed_end):
        raise FreqtradeIOGuardError("request must use the exact frozen timerange")
    if not runtime_image.startswith("freqtradeorg/freqtrade@sha256:"):
        raise FreqtradeIOGuardError("runtime image must use an immutable digest")
    if not runtime_command or any(not str(value).strip() for value in runtime_command):
        raise FreqtradeIOGuardError("runtime command must be explicit and non-empty")
    if _contains_symlink(input_path):
        raise FreqtradeIOGuardError("input root must not contain a symlink")
    for other in [output_path, *forbidden_paths]:
        if _overlap(input_path, other):
            raise FreqtradeIOGuardError("formal data, output, and forbidden roots overlap")
    for index, left in enumerate(forbidden_paths):
        if _overlap(output_path, left):
            raise FreqtradeIOGuardError("formal data, output, and forbidden roots overlap")
        for right in forbidden_paths[index + 1 :]:
            if _overlap(left, right):
                raise FreqtradeIOGuardError("formal data, output, and forbidden roots overlap")

    file_entries: list[dict[str, Any]] = []
    for value in allowed_files:
        source = Path(value)
        if _contains_symlink(source, stop_at=input_path):
            raise FreqtradeIOGuardError(f"allowed data path contains a symlink: {source}")
        resolved = source.resolve(strict=True)
        if not resolved.is_file() or not resolved.is_relative_to(input_path):
            raise FreqtradeIOGuardError(f"allowed file escapes input root: {source}")
        content = resolved.read_bytes()
        file_entries.append(
            {
                "path": str(resolved),
                "relativePath": resolved.relative_to(input_path).as_posix(),
                "sizeBytes": len(content),
                "sha256": _sha256_bytes(content),
            }
        )
    file_entries.sort(key=lambda row: row["relativePath"])
    if not file_entries:
        raise FreqtradeIOGuardError("at least one exact allowed file is required")

    core: dict[str, Any] = {
        "schemaVersion": "alphapilot_freqtrade_io_contract_v1",
        "status": "ready",
        "inputRoot": str(input_path),
        "outputRoot": str(output_path),
        "allowedStart": allowed_start,
        "allowedEndExclusive": allowed_end,
        "requestedStart": requested_start,
        "requestedEndExclusive": requested_end,
        "allowedFileCount": len(file_entries),
        "allowedFiles": file_entries,
        "forbiddenRoots": forbidden,
        "runtimeImage": runtime_image,
        "runtimeCommand": [str(value) for value in runtime_command],
        "networkMode": "none",
        "repositoryReadOnly": True,
        "lockedOosMounted": False,
    }
    return {**core, "contractHash": _canonical_hash(core)}


def _append_access_event(
    log_path: Path,
    *,
    contract_hash: str,
    attempted_path: Path,
    purpose: str,
    allowed: bool,
    reason: str,
    content_hash: str | None,
) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    previous_hash: str | None = None
    if log_path.exists():
        lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]
        if lines:
            previous_hash = str(json.loads(lines[-1])["eventHash"])
    core = {
        "schemaVersion": "alphapilot_freqtrade_io_access_event_v1",
        "recordedAt": datetime.now(timezone.utc).isoformat(),
        "contractHash": contract_hash,
        "attemptedPath": str(attempted_path.absolute()),
        "purpose": purpose,
        "allowed": allowed,
        "reason": reason,
        "contentSha256": content_hash,
        "previousEventHash": previous_hash,
    }
    event = {**core, "eventHash": _canonical_hash(core)}
    with log_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def guarded_read_bytes(
    contract: Mapping[str, Any],
    path: Path,
    access_log: Path,
    *,
    purpose: str,
) -> bytes:
    attempted = Path(path)
    contract_hash = str(contract.get("contractHash") or "")
    if not contract_hash or not purpose.strip():
        raise FreqtradeIOGuardError("contract hash and access purpose are required")
    if _contains_symlink(attempted):
        _append_access_event(
            access_log,
            contract_hash=contract_hash,
            attempted_path=attempted,
            purpose=purpose,
            allowed=False,
            reason="symlink_rejected",
            content_hash=None,
        )
        raise FreqtradeIOGuardError("data path contains a symlink")
    try:
        resolved = attempted.resolve(strict=True)
    except OSError as exc:
        _append_access_event(
            access_log,
            contract_hash=contract_hash,
            attempted_path=attempted,
            purpose=purpose,
            allowed=False,
            reason="path_missing_or_escape",
            content_hash=None,
        )
        raise FreqtradeIOGuardError("data path is missing or escapes the root") from exc
    for root in (Path(value) for value in contract.get("forbiddenRoots", [])):
        if resolved.is_relative_to(root):
            _append_access_event(
                access_log,
                contract_hash=contract_hash,
                attempted_path=attempted,
                purpose=purpose,
                allowed=False,
                reason="forbidden_root",
                content_hash=None,
            )
            raise FreqtradeIOGuardError("data path is inside a forbidden root")
    allowed = {str(row["path"]): str(row["sha256"]) for row in contract["allowedFiles"]}
    expected_hash = allowed.get(str(resolved))
    if expected_hash is None:
        _append_access_event(
            access_log,
            contract_hash=contract_hash,
            attempted_path=attempted,
            purpose=purpose,
            allowed=False,
            reason="not_allowlisted",
            content_hash=None,
        )
        raise FreqtradeIOGuardError("data path is not in the exact allowlist")
    content = resolved.read_bytes()
    actual_hash = _sha256_bytes(content)
    if actual_hash != expected_hash:
        _append_access_event(
            access_log,
            contract_hash=contract_hash,
            attempted_path=attempted,
            purpose=purpose,
            allowed=False,
            reason="content_hash_mismatch",
            content_hash=actual_hash,
        )
        raise FreqtradeIOGuardError("allowlisted data content hash changed")
    _append_access_event(
        access_log,
        contract_hash=contract_hash,
        attempted_path=attempted,
        purpose=purpose,
        allowed=True,
        reason="allowlisted_read",
        content_hash=actual_hash,
    )
    return content


def audit_freqtrade_access_log(
    contract: Mapping[str, Any], access_log: Path
) -> dict[str, Any]:
    events = [
        json.loads(line)
        for line in access_log.read_text(encoding="utf-8").splitlines()
        if line
    ] if access_log.exists() else []
    expected_previous: str | None = None
    chain_valid = True
    contract_hash = str(contract["contractHash"])
    for event in events:
        core = {key: value for key, value in event.items() if key != "eventHash"}
        if (
            event.get("previousEventHash") != expected_previous
            or event.get("eventHash") != _canonical_hash(core)
            or event.get("contractHash") != contract_hash
        ):
            chain_valid = False
        expected_previous = str(event.get("eventHash"))
    allowed_count = sum(bool(event.get("allowed")) for event in events)
    unauthorized_count = sum(not bool(event.get("allowed")) for event in events)
    status = "passed" if chain_valid and unauthorized_count == 0 else "failed"
    return {
        "schemaVersion": "alphapilot_freqtrade_io_access_audit_v1",
        "status": status,
        "contractHash": contract_hash,
        "eventCount": len(events),
        "allowedReadCount": allowed_count,
        "unauthorizedAttemptCount": unauthorized_count,
        "hashChainValid": chain_valid,
        "lastEventHash": expected_previous,
    }
