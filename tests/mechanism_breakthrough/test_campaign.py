from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alphapilot.mechanism_breakthrough.campaign import run_mechanism_breakthrough_campaign


def _write_market(root: Path, symbol: str, timeframe: str, rows: int) -> None:
    frequency = "h" if timeframe == "1h" else "4h"
    dates = pd.date_range("2024-01-01", periods=rows, freq=frequency, tz="UTC")
    values = [100.0 + index * 0.01 for index in range(rows)]
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": values,
            "high": [value + 0.2 for value in values],
            "low": [value - 0.2 for value in values],
            "close": values,
            "volume": [1000.0] * rows,
            "instrument_id": [symbol] * rows,
            "timeframe": [timeframe] * rows,
        }
    )
    target = root / "okx" / "swap" / "ohlcv" / symbol / timeframe / f"1-{rows}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(target, index=False)


def test_campaign_emits_honest_zero_survivor_evidence(tmp_path: Path) -> None:
    data_root = tmp_path / "canonical"
    for symbol in ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "LINK-USDT-SWAP", "LTC-USDT-SWAP"):
        _write_market(data_root, symbol, "1h", 260)
        _write_market(data_root, symbol, "4h", 260)
    package_root = tmp_path / "reference"
    (package_root / "references" / "price_action_docs").mkdir(parents=True)
    (package_root / "references" / "price_action_docs" / "source.txt").write_text(
        "bounded source summary", encoding="utf-8"
    )
    output = tmp_path / "output"

    result = run_mechanism_breakthrough_campaign(
        data_root=data_root,
        reference_package_root=package_root,
        output_root=output,
        inherited_full_backtests=91,
        frozen_at="2026-07-20T00:00:00Z",
        code_commit="deadbeef",
    )

    assert result["status"] == "completed_zero_qualified_candidates"
    assert result["lockedOosReadCount"] == 0
    assert (output / "source_inventory.json").is_file()
    assert (output / "artifact_similarity_matrix.parquet").is_file()
    assert (output / "prefilter_gate_matrix.csv").is_file()
    assert json.loads((output / "release_inventory.json").read_text(encoding="utf-8"))[
        "releaseCount"
    ] == 0
    assert json.loads((output / "statistical_matrix.json").read_text(encoding="utf-8"))[
        "status"
    ].startswith("not_run")


def test_prepare_only_freezes_identity_without_reading_economic_results(tmp_path: Path) -> None:
    data_root = tmp_path / "canonical"
    for symbol in ("BTC-USDT-SWAP", "ETH-USDT-SWAP"):
        _write_market(data_root, symbol, "1h", 260)
        _write_market(data_root, symbol, "4h", 260)
    package_root = tmp_path / "reference"
    package_root.mkdir()
    output = tmp_path / "output"

    result = run_mechanism_breakthrough_campaign(
        data_root=data_root,
        reference_package_root=package_root,
        output_root=output,
        inherited_full_backtests=91,
        frozen_at="2026-07-20T00:00:00Z",
        code_commit="deadbeef",
        prepare_only=True,
    )

    assert result["status"] == "preregistered_not_run"
    assert result["economicResultReadCount"] == 0
    assert result["lockedOosReadCount"] == 0
    assert list((output / "preregistrations").glob("*.json"))
    assert not (output / "candidate_results.parquet").exists()
