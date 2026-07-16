from __future__ import annotations

import re

from alphapilot.minimal_research_campaign.forward_collection import (
    build_forward_collection_plan,
)
from alphapilot.minimal_research_campaign.snapshot import build_snapshot_manifest


def test_shared_snapshot_references_existing_files_without_copying() -> None:
    core = {
        "coreUniverseHash": "core-hash",
        "members": [{"instrumentId": "BTC-USDT-SWAP"}],
        "commonCutoffByTimeframe": {"4h": "2026-07-15T00:00:00+00:00"},
    }
    references = [
        {
            "instrumentId": "BTC-USDT-SWAP",
            "timeframe": "1h",
            "path": "_alphapilot/canonical/okx/swap/ohlcv/BTC-USDT-SWAP/1h/data.parquet",
            "sha256": "def",
            "effectiveBacktestStart": "2021-01-01T00:00:00+00:00",
        },
        {
            "instrumentId": "BTC-USDT-SWAP",
            "timeframe": "4h",
            "path": "_alphapilot/canonical/okx/swap/ohlcv/BTC-USDT-SWAP/4h/data.parquet",
            "sha256": "abc",
            "effectiveBacktestStart": "2020-01-01T00:00:00+00:00",
        }
    ]

    first = build_snapshot_manifest(core, references, git_commit="deadbeef")
    second = build_snapshot_manifest(core, references, git_commit="deadbeef")

    assert first["snapshotId"] == second["snapshotId"]
    assert re.fullmatch(r"minimal_snapshot_[0-9a-f]{24}", first["snapshotId"])
    assert first["storageMode"] == "manifest_only"
    assert first["physicalCopiesCreated"] == 0
    assert first["datasetReferences"] == references
    assert first["effectiveStarts"] == {
        "BTC-USDT-SWAP": {
            "1h": "2021-01-01T00:00:00+00:00",
            "4h": "2020-01-01T00:00:00+00:00",
        }
    }


def test_forward_collection_keeps_missing_history_unavailable() -> None:
    plan = build_forward_collection_plan(
        available_data_types={"OHLCV", "Funding"},
        start_at="2026-07-16T00:00:00+00:00",
    )

    assert plan["forwardDataCannotBackfillHistory"] is True
    assert plan["dataTypes"]["Funding"]["status"] == "available_existing"
    assert plan["dataTypes"]["Open Interest"]["status"] == "forward_only_missing_history"
    assert plan["dataTypes"]["Liquidation"]["historicalValue"] is None
