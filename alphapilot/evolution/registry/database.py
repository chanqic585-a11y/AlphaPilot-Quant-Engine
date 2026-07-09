"""SQLite connection helpers for the local evolution registry."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .migrations import apply_migrations

DEFAULT_REGISTRY_PATH = Path("data/evolution_registry.sqlite")


def connect_registry(
    path: Path | str = DEFAULT_REGISTRY_PATH,
    *,
    initialize: bool = True,
) -> sqlite3.Connection:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    if initialize:
        apply_migrations(connection)
    return connection
