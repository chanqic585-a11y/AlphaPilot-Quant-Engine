from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alphapilot.minimal_research_campaign.data_layer_builder import (
    build_minimal_data_layer,
    discover_authoritative_ohlcv,
)


def _write_ohlcv(path: Path, instrument: str, timeframe: str, periods: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2022-01-01", periods=periods, freq=timeframe, tz="UTC")
    values = pd.Series(range(periods), dtype="float64")
    pd.DataFrame(
        {
            "timestamp_ms": (dates.astype("int64") // 1_000_000).astype("int64"),
            "date": dates,
            "open": 100.0 + values,
            "high": 101.0 + values,
            "low": 99.0 + values,
            "close": 100.5 + values,
            "volume": 10.0 + values,
            "confirmed": True,
            "exchange": "okx",
            "market_type": "swap",
            "instrument_id": instrument,
            "timeframe": timeframe,
        }
    ).to_parquet(path, index=False)


def test_discovery_reuses_largest_authoritative_partition(tmp_path: Path) -> None:
    base = tmp_path / "_alphapilot" / "canonical" / "okx" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "4h"
    _write_ohlcv(base / "small.parquet", "BTC-USDT-SWAP", "4h", 4)
    large = base / "large.parquet"
    _write_ohlcv(large, "BTC-USDT-SWAP", "4h", 8)

    discovered = discover_authoritative_ohlcv(tmp_path, timeframes=("4h",))

    assert len(discovered) == 1
    assert Path(discovered[0]["path"]) == large.resolve()
    assert discovered[0]["rowCount"] == 8


def test_builder_writes_reports_and_manifest_without_copying_market_data(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    repo_root = tmp_path / "repo"
    for instrument_index, instrument in enumerate(("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")):
        for timeframe in ("1h", "4h"):
            path = data_root / "_alphapilot" / "canonical" / "okx" / "swap" / "ohlcv" / instrument / timeframe / "all.parquet"
            _write_ohlcv(path, instrument, timeframe, 220 + instrument_index)
    before = sorted(data_root.rglob("*.parquet"))

    result = build_minimal_data_layer(
        data_root=data_root,
        repo_root=repo_root,
        target_size=2,
        minimum_history_months=0,
        git_commit="deadbeef",
    )

    after = sorted(data_root.rglob("*.parquet"))
    assert after == before
    assert result["coreUniverse"]["memberCount"] == 2
    assert result["sharedSnapshot"]["physicalCopiesCreated"] == 0
    assert (repo_root / "reports" / "minimal_data_layer" / "core_universe.json").is_file()
    assert (repo_root / "reports" / "minimal_data_layer" / "core_universe.csv").is_file()
    assert (repo_root / "reports" / "minimal_data_layer" / "core_universe_selection.md").is_file()
    snapshot_path = repo_root / "research" / "data_snapshots" / f"{result['sharedSnapshot']['snapshotId']}.json"
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["storageMode"] == "manifest_only"
    assert len(payload["datasetReferences"]) == 4
