from __future__ import annotations

import json
from pathlib import Path
import re

import pandas as pd
import pytest

from alphapilot.data_foundation.funding_carry_catalog import (
    ArtifactIntegrityError,
    FundingCarryCatalog,
    FundingHistoryConsolidator,
    OkxSpotHistoryCollector,
)
from alphapilot.evolution.registry.hashing import sha256_file


def _canonical_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp_ms": [0, 3_600_000],
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "vol": [10.0, 12.0],
            "volCcy": [10.0, 12.0],
            "volCcyQuote": [1_000.0, 1_200.0],
            "confirm": [1, 1],
            "availableAt": [
                "1970-01-01T01:00:00+00:00",
                "1970-01-01T02:00:00+00:00",
            ],
            "ingestedAt": ["2026-07-19T00:00:00+00:00"] * 2,
        }
    )


def _write_v34a_partition(root: Path) -> tuple[Path, Path]:
    output = root / "okx_official_v1" / "canonical" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "1h" / "fixture.parquet"
    output.parent.mkdir(parents=True)
    _canonical_frame().to_parquet(output, index=False)
    manifest = root / "okx_official_v1" / "manifests" / "BTC-USDT-SWAP-1h-fixture.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": "okx_official_v1_partition_manifest_v1",
                "instrumentId": "BTC-USDT-SWAP",
                "timeframe": "1h",
                "sourceEndpoint": "https://openapi.okx.com/api/v5/market/history-candles",
                "outputPath": str(output.resolve()),
                "outputSha256": sha256_file(output),
            }
        ),
        encoding="utf-8",
    )
    return output, manifest


def test_catalog_reuses_verified_v34a_perpetual_partition(tmp_path: Path) -> None:
    output, manifest = _write_v34a_partition(tmp_path)

    artifact = FundingCarryCatalog(tmp_path).perpetual_partition(
        instrument_id="BTC-USDT-SWAP", timeframe="1h"
    )

    assert artifact.path == output.resolve()
    assert artifact.sha256 == sha256_file(output)
    assert artifact.manifest_path == manifest.resolve()
    assert artifact.source_type == "okx_perpetual_ohlcv"


def test_catalog_rejects_tampered_perpetual_partition(tmp_path: Path) -> None:
    output, _ = _write_v34a_partition(tmp_path)
    output.write_bytes(output.read_bytes() + b"tamper")

    with pytest.raises(ArtifactIntegrityError, match="content_hash_mismatch"):
        FundingCarryCatalog(tmp_path).perpetual_partition(
            instrument_id="BTC-USDT-SWAP", timeframe="1h"
        )


def test_catalog_relocates_stale_manifest_path_only_by_unique_hash(
    tmp_path: Path,
) -> None:
    output, manifest = _write_v34a_partition(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["outputPath"] = str(
        tmp_path / "stale-encoded-root" / output.name
    )
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    artifact = FundingCarryCatalog(tmp_path).perpetual_partition(
        instrument_id="BTC-USDT-SWAP", timeframe="1h"
    )

    assert artifact.path == output.resolve()
    assert artifact.details["pathResolution"] == "warehouse_unique_sha256"


def _write_funding_sources(root: Path) -> None:
    v36_raw = root / "_alphapilot" / "raw" / "okx" / "swap" / "funding_history" / "BTC-USDT-SWAP" / "month.zip"
    v36_raw.parent.mkdir(parents=True)
    v36_raw.write_bytes(b"official archive bytes")
    v36_canonical = root / "_alphapilot" / "canonical" / "okx" / "swap" / "funding" / "BTC-USDT-SWAP" / "month.parquet"
    v36_canonical.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "instrument_id": ["BTC-USDT-SWAP", "BTC-USDT-SWAP"],
            "funding_rate": [0.0001, -0.0002],
            "timestamp_ms": [0, 28_800_000],
            "available_at": [
                "1970-01-01T00:00:00+00:00",
                "1970-01-01T08:00:00+00:00",
            ],
        }
    ).to_parquet(v36_canonical, index=False)
    v36_manifest = root / "_alphapilot" / "evidence" / "okx" / "funding_history" / "manifests" / "fixture.json"
    v36_manifest.parent.mkdir(parents=True)
    v36_manifest.write_text(
        json.dumps(
            {
                "schemaVersion": "v36_okx_historical_funding_v1",
                "status": "completed",
                "sameExchangeOnly": True,
                "zeroFillUsed": False,
                "artifacts": [
                    {
                        "artifactType": "monthlyFundingArchive",
                        "instrumentId": "BTC-USDT-SWAP",
                        "rawPath": str(v36_raw.resolve()),
                        "canonicalPath": str(v36_canonical.resolve()),
                        "archiveSha256": sha256_file(v36_raw),
                        "rowCount": 2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    v34_canonical = root / "okx_official_v1" / "canonical" / "okx" / "swap" / "funding" / "BTC-USDT-SWAP" / "recent.parquet"
    v34_canonical.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "instrumentId": ["BTC-USDT-SWAP", "BTC-USDT-SWAP"],
            "fundingTime": [28_800_000, 57_600_000],
            "realizedRate": [-0.0002, 0.0003],
            "realizedRateAvailableAt": [
                "1970-01-01T08:00:00+00:00",
                "1970-01-01T16:00:00+00:00",
            ],
        }
    ).to_parquet(v34_canonical, index=False)
    v34_manifest = root / "okx_official_v1" / "manifests" / "v34b" / "funding-fixture.json"
    v34_manifest.parent.mkdir(parents=True)
    v34_manifest.write_text(
        json.dumps(
            {
                "schemaVersion": "okx_official_v1_v34b_funding_manifest_v1",
                "publicDataOnly": True,
                "artifacts": [
                    {
                        "instrumentId": "BTC-USDT-SWAP",
                        "path": str(v34_canonical.resolve()),
                        "sha256": sha256_file(v34_canonical),
                        "rows": 2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_funding_consolidator_verifies_and_deduplicates_v36_and_v34b(
    tmp_path: Path,
) -> None:
    _write_funding_sources(tmp_path)

    result = FundingHistoryConsolidator(tmp_path).consolidate(
        "BTC-USDT-SWAP", observed_at="2026-07-19T00:00:00+00:00"
    )
    reused = FundingHistoryConsolidator(tmp_path).consolidate(
        "BTC-USDT-SWAP", observed_at="2026-07-19T01:00:00+00:00"
    )

    assert result.status == "consolidated"
    assert reused.status == "reused"
    assert result.artifact.row_count == 3
    frame = pd.read_parquet(result.artifact.path)
    assert list(frame["timestamp_ms"]) == [0, 28_800_000, 57_600_000]
    assert list(frame["funding_rate"]) == [0.0001, -0.0002, 0.0003]
    persisted = json.loads(
        result.artifact.manifest_path.read_text(encoding="utf-8")
    )
    assert persisted["zeroFillUsed"] is False
    assert persisted["sameExchangeOnly"] is True
    assert persisted["candidateCount"] == 0
    assert len(persisted["sources"]) == 2
    assert re.fullmatch(
        r"\d+-\d+-[0-9a-f]{16}\.parquet", result.artifact.path.name
    )
    assert re.fullmatch(
        r"BTC-USDT-SWAP-[0-9a-f]{20}\.json",
        result.artifact.manifest_path.name,
    )


class _SpotClient:
    base_url = "https://openapi.okx.com"

    def __init__(self) -> None:
        self.calls = 0
        self.request_audit_records: list[dict[str, object]] = []

    def history_candle_rows(self, **_: object) -> tuple[list[list[object]], int]:
        self.calls += 1
        return (
            [
                ["0", "100", "101", "99", "100.5", "10", "10", "1000", "1"],
                ["3600000", "101", "102", "100", "101.5", "12", "12", "1200", "1"],
            ],
            1,
        )


def test_spot_collector_writes_content_addressed_partition_and_reuses_it(
    tmp_path: Path,
) -> None:
    client = _SpotClient()
    collector = OkxSpotHistoryCollector(
        warehouse_root=tmp_path,
        client=client,
        timeframe="1h",
        requested_start_ms=0,
    )

    first = collector.collect("BTC-USDT", observed_at="2026-07-19T00:00:00+00:00")
    second = collector.collect("BTC-USDT", observed_at="2026-07-19T01:00:00+00:00")

    assert first.status == "collected"
    assert second.status == "reused"
    assert client.calls == 1
    assert first.artifact.path.is_file()
    assert first.artifact.manifest_path.is_file()
    assert first.artifact.sha256 == sha256_file(first.artifact.path)
    persisted = json.loads(first.artifact.manifest_path.read_text(encoding="utf-8"))
    assert persisted["instrumentType"] == "SPOT"
    assert persisted["publicDataOnly"] is True
    assert persisted["candidateCount"] == 0
    assert persisted["orderCount"] == 0
    assert re.fullmatch(
        r"\d+-\d+-[0-9a-f]{16}\.parquet", first.artifact.path.name
    )
    assert re.fullmatch(
        r"BTC-USDT-1h-[0-9a-f]{20}\.json",
        first.artifact.manifest_path.name,
    )
    raw_path = Path(persisted["rawPath"])
    assert re.fullmatch(r"rows-[0-9a-f]{20}\.json", raw_path.name)
