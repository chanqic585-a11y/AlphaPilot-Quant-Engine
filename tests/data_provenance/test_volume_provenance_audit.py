from __future__ import annotations

import json

import pandas as pd
from openpyxl import Workbook

from alphapilot.data_provenance.volume_provenance_audit import (
    audit_volume_provenance_records,
    build_exchange_identity_audit,
    discover_volume_provenance_records,
)


def test_audit_reports_route_counts_without_guessing_units() -> None:
    records = [
        {
            "datasetId": "btc_4h",
            "instrumentId": "BTC-USDT-SWAP",
            "timeframe": "4h",
            "rawColumnNames": ["volume_quote_currency"],
            "selectedVolumeColumn": "volume_quote_currency",
            "sourceFileHash": "hash-btc",
            "evidenceRefs": ["raw_multicolumn_file", "canonical_reader_mapping"],
        },
        {
            "datasetId": "eth_4h",
            "instrumentId": "ETH-USDT-SWAP",
            "timeframe": "4h",
            "rawColumnNames": ["volume"],
            "selectedVolumeColumn": "volume",
            "sourceFileHash": "hash-eth",
            "evidenceRefs": [],
        },
    ]
    audit = audit_volume_provenance_records(records)

    assert audit["datasetCount"] == 2
    assert audit["verifiedExactTurnoverCount"] == 1
    assert audit["unavailableCount"] == 1
    assert audit["auditHash"].startswith("volume_provenance_audit_")


def test_exchange_identity_is_a_separate_release_gate() -> None:
    audit = build_exchange_identity_audit(
        research_exchange="unverified_local_exchange",
        ohlcv_exchange="unverified_local_exchange",
        funding_exchange="binance",
        demo_execution_exchange="okx",
    )

    assert audit["sameExchange"] is False
    assert audit["crossExchangePortabilityStatus"] == "not_verified"
    assert audit["releaseEligible"] is False


def test_discovery_binds_raw_header_reader_mapping_and_manifest(tmp_path) -> None:
    raw_root = tmp_path / "raw"
    canonical_root = tmp_path / "canonical"
    raw_symbol = raw_root / "swap_candles_4H" / "BTC_USDT_SWAP"
    raw_symbol.mkdir(parents=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(
        [
            "timestamp_ms",
            "open",
            "high",
            "low",
            "close",
            "volume_base_or_contracts",
            "volume_quote_currency",
        ]
    )
    worksheet.append([1, 1.0, 2.0, 0.5, 1.5, 10.0, 15.0])
    raw_path = raw_symbol / "BTC_USDT_SWAP_ALL.xlsx"
    workbook.save(raw_path)

    canonical_symbol = canonical_root / "BTC-USDT-SWAP" / "4h"
    canonical_symbol.mkdir(parents=True)
    canonical_path = canonical_symbol / "part-000.parquet"
    pd.DataFrame(
        {
            "date": ["2024-01-01T00:00:00Z"],
            "open": [1.0],
            "high": [2.0],
            "low": [0.5],
            "close": [1.5],
            "volume": [15.0],
        }
    ).to_parquet(canonical_path, index=False)

    manifest_path = tmp_path / "data_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "datasetType": "ohlcv",
                        "instrumentId": "BTC-USDT-SWAP",
                        "timeframe": "4h",
                        "exchange": "unverified_local_exchange",
                        "rowCount": 1,
                        "start": "2024-01-01T00:00:00Z",
                        "end": "2024-01-01T00:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    records = discover_volume_provenance_records(
        manifest_path=manifest_path,
        raw_root=raw_root,
        canonical_root=canonical_root,
        instruments=["BTC-USDT-SWAP"],
        timeframes=["4h"],
    )

    assert len(records) == 1
    record = records[0]
    assert record["selectedVolumeColumn"] == "volume_quote_currency"
    assert record["selectedVolumeColumnIndex"] == 6
    assert record["declaredVolumeUnit"] == "quote_asset"
    assert record["sourceFileHash"]
    assert record["canonicalPath"] == str(canonical_path.resolve())
    assert record["canonicalReaderMapping"] == {
        "canonicalVolumeField": "volume",
        "rawVolumeField": "volume_quote_currency",
    }
    assert record["sourceExchange"] == "unverified_local_exchange"
    assert record["evidenceRefs"] == [
        "raw_multicolumn_file",
        "manifest",
        "canonical_reader_mapping",
    ]
