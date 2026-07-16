from __future__ import annotations

from pathlib import Path

import pandas as pd

from alphapilot.derivatives_data.historical_pit_reports import build_stage3_reports


def _write_funding_partition(root: Path) -> None:
    path = root / "normalized" / "binance" / "swap" / "funding" / "BTC-USDT-SWAP.parquet"
    path.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "timestampUtc": "2024-01-01T00:00:00Z",
                "sourceTimestamp": "2024-01-01T00:00:00Z",
                "exchange": "binance",
                "marketType": "swap",
                "instrumentId": "BTC-USDT-SWAP",
                "fundingRate": 0.0001,
            },
            {
                "timestampUtc": "2024-01-01T08:00:00Z",
                "sourceTimestamp": "2024-01-01T08:00:00Z",
                "exchange": "binance",
                "marketType": "swap",
                "instrumentId": "BTC-USDT-SWAP",
                "fundingRate": 0.0002,
            },
        ]
    ).to_parquet(path, index=False)


def test_stage3_reports_do_not_promote_incomplete_funding_to_formal(tmp_path: Path) -> None:
    _write_funding_partition(tmp_path)

    reports = build_stage3_reports(
        data_root=tmp_path,
        checked_at="2026-07-16T00:00:00Z",
    )

    assert reports["familyB"]["status"] != "formal_ready"
    assert "perpetual_ohlcv" in reports["familyB"]["missingDataTypes"]
    assert reports["pitAudit"]["historicalFormalReady"] is False
    assert reports["pitAudit"]["currentTopNBackfill"] is False
    assert reports["readiness"]["qlibCampaignMayRun"] is False
    assert reports["readiness"]["threeDirectionCampaignMayRun"] is False

    quality = reports["qualityByInstrument"][0]
    assert quality["imputedZeroCount"] == 0
    assert quality["contentHash"]
    assert "missing_strict_availability_clocks" in quality["blockers"]


def test_stage3_empty_data_is_honest_and_future_collection_only(tmp_path: Path) -> None:
    reports = build_stage3_reports(
        data_root=tmp_path,
        checked_at="2026-07-16T00:00:00Z",
    )

    assert reports["familyB"]["status"] == "unavailable"
    assert reports["pitAudit"]["futureCollectionReady"] is True
    assert reports["pitAudit"]["historicalFormalReady"] is False
    assert reports["pitCoverage"] == []
    assert reports["readiness"]["status"] == "data_not_ready"
