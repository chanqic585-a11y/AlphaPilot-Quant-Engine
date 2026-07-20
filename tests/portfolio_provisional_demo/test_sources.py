from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pandas as pd

from alphapilot.portfolio_provisional_demo.sources import (
    load_demo_universe_snapshot,
    load_research_instruments,
    verify_patch_instruction,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_research_instruments_are_loaded_from_frozen_policy_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "pair_14d_cooldown.parquet"
    pd.DataFrame(
        {
            "pair": ["BTC/USDT:USDT", "ETH/USDT:USDT", "BTC/USDT:USDT"],
            "netR": [1.0, -1.0, 0.5],
        }
    ).to_parquet(ledger, index=False)

    assert load_research_instruments(ledger) == [
        "BTC-USDT-SWAP",
        "ETH-USDT-SWAP",
    ]


def test_demo_universe_sqlite_is_read_only_and_keeps_counts_separate(
    tmp_path: Path,
) -> None:
    database = tmp_path / "demo.sqlite"
    connection = sqlite3.connect(database)
    connection.execute(
        """
        CREATE TABLE DemoInstrumentUniverseCache (
          environment TEXT NOT NULL,
          publicManifestHash TEXT NOT NULL,
          authenticatedInstrumentHash TEXT NOT NULL,
          projectionJson TEXT NOT NULL,
          generatedAt TEXT NOT NULL,
          cacheTtlSeconds INTEGER NOT NULL,
          PRIMARY KEY(environment, publicManifestHash, authenticatedInstrumentHash)
        )
        """
    )
    projection = {
        "environment": "demo",
        "status": "usable",
        "blockers": [],
        "publicUniverseCount": 20,
        "demoAccountInstrumentCount": 116,
        "eligibleInstrumentIds": ["ETH-USDT-SWAP", "BTC-USDT-SWAP"],
    }
    connection.execute(
        "INSERT INTO DemoInstrumentUniverseCache VALUES (?, ?, ?, ?, ?, ?)",
        (
            "demo",
            "public_hash",
            "authenticated_hash",
            json.dumps(projection),
            "2026-07-20T00:00:00Z",
            300,
        ),
    )
    connection.commit()
    connection.close()
    before = _sha(database)

    snapshot = load_demo_universe_snapshot(database)

    assert _sha(database) == before
    assert snapshot["publicCount"] == 20
    assert snapshot["authenticatedCount"] == 116
    assert snapshot["runtimeInstruments"] == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    assert snapshot["runtimeCount"] == 2


def test_patch_instruction_hash_must_match_supplied_manifest(tmp_path: Path) -> None:
    instruction = tmp_path / "patch.md"
    manifest = tmp_path / "manifest.json"
    instruction.write_text("frozen patch\n", encoding="utf-8")
    manifest.write_text(
        json.dumps({"sha256": _sha(instruction), "filename": instruction.name}),
        encoding="utf-8",
    )

    receipt = verify_patch_instruction(instruction, manifest)

    assert receipt["verified"] is True
    assert receipt["sha256"] == _sha(instruction)
