import json
from pathlib import Path

import pandas as pd

from alphapilot.research_screening.prepare_data import (
    collect_binance_funding,
    select_canonical_ohlcv,
)


def test_select_canonical_ohlcv_reuses_largest_existing_partition(tmp_path: Path) -> None:
    base = tmp_path / "canonical" / "user_local" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "1d"
    base.mkdir(parents=True)
    small = base / "small.parquet"
    large = base / "large.parquet"
    pd.DataFrame({"date": pd.date_range("2024-01-01", periods=2, tz="UTC")}).to_parquet(small)
    pd.DataFrame({"date": pd.date_range("2024-01-01", periods=5, tz="UTC")}).to_parquet(large)

    selected = select_canonical_ohlcv(tmp_path / "canonical", "BTC-USDT-SWAP", "1d")

    assert selected == large


def test_collect_funding_paginates_and_reuses_complete_raw_file(tmp_path: Path) -> None:
    calls: list[int] = []

    def fetch(_symbol: str, start_ms: int, _end_ms: int) -> list[dict[str, object]]:
        calls.append(start_ms)
        if len(calls) == 1:
            return [
                {"fundingTime": start_ms, "fundingRate": "0.001"},
                {"fundingTime": start_ms + 1000, "fundingRate": "0.002"},
            ]
        return []

    output = tmp_path / "funding.json"
    first = collect_binance_funding(
        instrument_id="BTC-USDT-SWAP",
        output_path=output,
        start_ms=1000,
        end_ms=3000,
        fetch_page=fetch,
    )
    second = collect_binance_funding(
        instrument_id="BTC-USDT-SWAP",
        output_path=output,
        start_ms=1000,
        end_ms=3000,
        fetch_page=fetch,
    )

    assert first["records"] == 2
    assert second["reused"] is True
    assert json.loads(output.read_text(encoding="utf-8"))["completeThroughMs"] == 3000
