"""Fail-closed timerange and input/output isolation for formal validation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from alphapilot.evolution.registry.hashing import sha256_file, stable_hash


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def build_formal_io_contract(
    *,
    input_root: Path,
    input_paths: Sequence[Path],
    output_root: Path,
    requested_start: str,
    requested_end: str,
    allowed_start: str,
    allowed_end: str,
    forbidden_roots: Sequence[Path] = (),
) -> dict[str, Any]:
    """Validate immutable inputs and an isolated output root before execution."""

    input_root = Path(input_root).resolve()
    output_root = Path(output_root).resolve()
    resolved_inputs = [Path(path).resolve() for path in input_paths]
    resolved_forbidden = [Path(path).resolve() for path in forbidden_roots]
    if not resolved_inputs:
        raise ValueError("at least one formal input is required")
    if _is_within(output_root, input_root):
        raise ValueError("output_root must be outside input_root")
    if any(_is_within(output_root, root) for root in resolved_forbidden):
        raise ValueError("output_root is inside a forbidden Locked OOS root")

    for path in resolved_inputs:
        if not path.is_file():
            raise ValueError(f"formal input does not exist: {path}")
        if not _is_within(path, input_root):
            raise ValueError(f"formal input is outside input_root: {path}")
        if any(_is_within(path, root) for root in resolved_forbidden):
            raise ValueError(f"Locked OOS content input is forbidden: {path}")

    requested_start_utc = _parse_utc(requested_start)
    requested_end_utc = _parse_utc(requested_end)
    allowed_start_utc = _parse_utc(allowed_start)
    allowed_end_utc = _parse_utc(allowed_end)
    if requested_start_utc >= requested_end_utc:
        raise ValueError("requested timerange start must precede end")
    if (
        requested_start_utc < allowed_start_utc
        or requested_end_utc > allowed_end_utc
    ):
        raise ValueError("requested timerange exceeds frozen boundary")

    inputs = [
        {
            "path": path.relative_to(input_root).as_posix(),
            "sha256": sha256_file(path),
            "sizeBytes": path.stat().st_size,
        }
        for path in sorted(resolved_inputs)
    ]
    contract: dict[str, Any] = {
        "schemaVersion": "formal_timerange_io_contract_v1",
        "status": "ready",
        "inputRoot": str(input_root),
        "inputCount": len(inputs),
        "inputs": inputs,
        "outputRoot": str(output_root),
        "outputIsolated": True,
        "requestedTimerange": {
            "start": requested_start_utc.isoformat().replace("+00:00", "Z"),
            "endExclusive": requested_end_utc.isoformat().replace("+00:00", "Z"),
        },
        "frozenBoundary": {
            "start": allowed_start_utc.isoformat().replace("+00:00", "Z"),
            "endExclusive": allowed_end_utc.isoformat().replace("+00:00", "Z"),
        },
        "lockedOosContentRead": False,
    }
    digest = stable_hash(contract)
    contract["contractHash"] = digest
    contract["contractId"] = f"formal_timerange_io_contract_{digest}"
    return contract
