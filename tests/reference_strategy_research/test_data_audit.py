from __future__ import annotations

import hashlib
from pathlib import Path

from alphapilot.reference_strategy_research.candidates import build_selected_candidates
from alphapilot.reference_strategy_research.data_audit import audit_candidate_data


def _row(path: Path, symbol: str, timeframe: str) -> dict[str, object]:
    payload = f"{symbol}-{timeframe}".encode("utf-8")
    path.write_bytes(payload)
    return {
        "datasetId": f"{symbol}-{timeframe}",
        "dataType": "ohlcv",
        "symbols": [symbol],
        "timeframe": timeframe,
        "sourcePath": str(path),
        "contentHash": hashlib.sha256(payload).hexdigest(),
    }


def test_existing_verified_timeframes_produce_no_download_plan(tmp_path: Path) -> None:
    candidates = build_selected_candidates(
        [
            {"candidateId": "ref_utc_session_range_breakout_1h_v1", "marketHypothesis": "x"},
            {"candidateId": "ref_pa_breakout_failure_second_entry_4h_v1", "marketHypothesis": "y"},
        ]
    )
    catalog = {
        "datasets": [
            _row(tmp_path / "btc-1h.parquet", "BTC-USDT-SWAP", "1h"),
            _row(tmp_path / "eth-1h.parquet", "ETH-USDT-SWAP", "1h"),
            _row(tmp_path / "btc-4h.parquet", "BTC-USDT-SWAP", "4h"),
            _row(tmp_path / "eth-4h.parquet", "ETH-USDT-SWAP", "4h"),
        ]
    }

    result = audit_candidate_data(
        candidates=candidates,
        catalog=catalog,
        instruments=("BTC-USDT-SWAP", "ETH-USDT-SWAP"),
    )

    assert result["ready"] is True
    assert result["downloadRequired"] is False
    assert result["missing"] == []
    assert result["reusedDatasetCount"] == 4


def test_missing_partition_is_an_explicit_gap_not_a_redownload(tmp_path: Path) -> None:
    candidates = build_selected_candidates(
        [{"candidateId": "ref_utc_session_range_breakout_1h_v1", "marketHypothesis": "x"}]
    )
    catalog = {
        "datasets": [_row(tmp_path / "btc-1h.parquet", "BTC-USDT-SWAP", "1h")]
    }

    result = audit_candidate_data(
        candidates=candidates,
        catalog=catalog,
        instruments=("BTC-USDT-SWAP", "ETH-USDT-SWAP"),
    )

    assert result["ready"] is False
    assert result["downloadRequired"] is True
    assert result["missing"] == [{"instrumentId": "ETH-USDT-SWAP", "timeframe": "1h"}]
    assert result["reusedDatasetCount"] == 1
