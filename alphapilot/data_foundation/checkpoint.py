"""Atomic JSON checkpoints for resumable data jobs."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def write_json_atomic(
    path: Path,
    value: Any,
    *,
    replace_attempts: int = 20,
    retry_delay_seconds: float = 0.1,
) -> None:
    if replace_attempts <= 0:
        raise ValueError("replace_attempts must be positive")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    for attempt in range(replace_attempts):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt + 1 >= replace_attempts:
                raise
            time.sleep(max(0.0, retry_delay_seconds))


def pause_requested(path: Path | None) -> bool:
    return bool(path and path.exists())
