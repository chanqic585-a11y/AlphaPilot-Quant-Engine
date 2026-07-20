"""Path rules for generated candidate run files."""

from __future__ import annotations

from pathlib import Path


SENSITIVE_PARTS = frozenset({"credential", "credentials", "secret", "secrets", "api_key"})


def validate_candidate_path(candidate_path: Path, *, run_directory: Path) -> Path:
    candidate = Path(candidate_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("candidate path must stay inside the run directory")
    if any(part.lower() in SENSITIVE_PARTS for part in candidate.parts):
        raise ValueError("candidate path may not target credential material")
    root = Path(run_directory).resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("candidate path escaped the run directory") from exc
    return resolved
