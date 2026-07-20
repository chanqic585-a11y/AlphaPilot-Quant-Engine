from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from alphapilot.data_foundation.okx_official_v1_forward import (
    OkxOfficialV1ForwardCollector,
    normalize_funding_rows,
)
from alphapilot.evolution.registry.hashing import sha256_file


class FakePublicClient:
    def __init__(self, *, fail_stream: str | None = None) -> None:
        self.base_url = "https://openapi.okx.com"
        self.request_audit_records: list[dict[str, object]] = []
        self.calls: list[str] = []
        self.fail_stream = fail_stream

    def _record(self, name: str) -> None:
        self.calls.append(name)
        if self.fail_stream == name:
            self.fail_stream = None
            raise RuntimeError(f"planned_{name}_failure")
        self.request_audit_records.append(
            {
                "path": f"/fake/{name}",
                "requestCompletedAt": "2026-07-19T01:00:00+00:00",
                "rawPayloadSha256": (name.encode("utf-8").hex() + "0" * 64)[:64],
                "responseCode": "0",
            }
        )

    def public_instruments(self, *, instrument_type: str = "SWAP") -> list[dict[str, str]]:
        assert instrument_type == "SWAP"
        self._record("instrument_metadata")
        return [
            {
                "instId": "BTC-USDT-SWAP",
                "instType": "SWAP",
                "instFamily": "BTC-USDT",
                "uly": "BTC-USDT",
                "settleCcy": "USDT",
                "ctVal": "0.01",
                "ctMult": "1",
                "ctValCcy": "BTC",
                "ctType": "linear",
                "listTime": "1600000000000",
                "expTime": "",
                "tickSz": "0.1",
                "lotSz": "0.01",
                "minSz": "0.01",
                "state": "live",
                "ruleType": "normal",
                "upcChg": "[{\"param\":\"tickSz\",\"newValue\":\"0.01\",\"effTime\":\"1800000000000\"}]",
            },
            {
                "instId": "ETH-USDT-SWAP",
                "instType": "SWAP",
                "instFamily": "ETH-USDT",
                "uly": "ETH-USDT",
                "settleCcy": "USDT",
                "ctVal": "0.1",
                "ctMult": "1",
                "ctValCcy": "ETH",
                "ctType": "linear",
                "listTime": "1600000000000",
                "expTime": "",
                "tickSz": "0.01",
                "lotSz": "0.01",
                "minSz": "0.01",
                "state": "live",
                "ruleType": "normal",
                "upcChg": "[]",
            },
        ]

    def funding_rate_history(self, **parameters: object) -> list[dict[str, str]]:
        self._record(f"funding_history:{parameters['instrument_id']}")
        if parameters.get("after_ms") is not None:
            return []
        return [
            {
                "fundingTime": "1767225600000",
                "fundingRate": "0.0001",
                "realizedRate": "0.00009",
                "formulaType": "withRate",
                "method": "current_period",
            }
        ]

    def current_funding_rate(self, *, instrument_id: str) -> list[dict[str, str]]:
        self._record(f"current_funding:{instrument_id}")
        return [{"instId": instrument_id, "fundingRate": "0.0001", "fundingTime": "1767225600000"}]

    def open_interest(self, *, instrument_id: str) -> list[dict[str, str]]:
        self._record(f"open_interest:{instrument_id}")
        return [{"instId": instrument_id, "oi": "123", "oiCcy": "1.23", "ts": "1767225600000"}]

    def mark_price(self, *, instrument_id: str) -> list[dict[str, str]]:
        self._record(f"mark_price:{instrument_id}")
        return [{"instId": instrument_id, "markPx": "100", "ts": "1767225600000"}]

    def index_ticker(self, *, instrument_id: str) -> list[dict[str, str]]:
        self._record(f"index_price:{instrument_id}")
        return [{"instId": instrument_id, "idxPx": "99.9", "ts": "1767225600000"}]

    def public_tickers(self, *, instrument_type: str = "SWAP") -> list[dict[str, str]]:
        assert instrument_type == "SWAP"
        self._record("ticker_spread")
        return [
            {"instId": "BTC-USDT-SWAP", "bidPx": "99.9", "askPx": "100.1", "last": "100", "ts": "1767225600000"},
            {"instId": "ETH-USDT-SWAP", "bidPx": "199.9", "askPx": "200.1", "last": "200", "ts": "1767225600000"},
        ]

    def order_book(self, *, instrument_id: str, depth: int = 5) -> list[dict[str, object]]:
        assert depth == 5
        self._record(f"order_book:{instrument_id}")
        return [{"asks": [["100.1", "2", "0", "1"]], "bids": [["99.9", "3", "0", "1"]], "ts": "1767225600000"}]


def test_funding_rows_preserve_causal_availability_and_source_metadata() -> None:
    rows = normalize_funding_rows(
        [
            {
                "fundingTime": "1767225600000",
                "fundingRate": "0.0001",
                "realizedRate": "0.00009",
                "formulaType": "withRate",
                "method": "current_period",
            }
        ],
        instrument_id="BTC-USDT-SWAP",
        retrieved_at="2026-01-01T00:05:00+00:00",
        source_hash="a" * 64,
    )

    assert rows == [
        {
            "instrumentId": "BTC-USDT-SWAP",
            "fundingTime": 1767225600000,
            "fundingRate": 0.0001,
            "realizedRate": 0.00009,
            "formulaType": "withRate",
            "method": "current_period",
            "realizedRateAvailableAt": "2026-01-01T00:00:00+00:00",
            "retrievedAt": "2026-01-01T00:05:00+00:00",
            "sourceHash": "a" * 64,
        }
    ]


def test_v34b_collector_is_immutable_resumable_and_data_only(tmp_path: Path) -> None:
    client = FakePublicClient()
    collector = OkxOfficialV1ForwardCollector(
        warehouse_root=tmp_path,
        client=client,
        instruments=("BTC-USDT-SWAP", "ETH-USDT-SWAP"),
        observed_at="2026-07-19T01:00:00+00:00",
    )

    first = collector.run()
    calls_after_first = list(client.calls)
    second = collector.run()

    assert first == second
    assert client.calls == calls_after_first
    assert first["status"] == "completed"
    assert first["scope"] == "v34b_public_data_only"
    assert first["instrumentMetadataCount"] == 2
    assert first["fundingInstrumentCount"] == 2
    assert set(first["forwardStreamsCompleted"]) == {
        "current_funding",
        "index_price",
        "instrument_state",
        "mark_price",
        "open_interest",
        "order_book_summary",
        "ticker_spread",
    }
    for field in (
        "candidateCount",
        "formalRunCount",
        "resultReadCount",
        "demoReleaseCount",
        "approvalCount",
        "orderCount",
    ):
        assert first[field] == 0
    assert first["demoArm"] is False

    manifest = Path(first["snapshotManifestPath"])
    assert manifest.is_file()
    assert sha256_file(manifest) == first["snapshotManifestSha256"]
    metadata = json.loads(Path(first["instrumentMetadataPath"]).read_text(encoding="utf-8"))
    assert metadata["historicalStateReconstructed"] is False
    assert metadata["pitHistoryBeginsAt"] == "2026-07-19T01:00:00+00:00"
    assert metadata["instruments"][0]["upcomingParameterChanges"][0]["param"] == "tickSz"

    funding = pd.read_parquet(first["fundingPaths"][0])
    assert "realizedRateAvailableAt" in funding.columns
    checkpoint = json.loads(Path(first["checkpointPath"]).read_text(encoding="utf-8"))
    assert checkpoint["status"] == "completed"
    assert set(checkpoint["completedStreams"]) >= {
        "instrument_metadata",
        "funding_history",
        "open_interest",
    }


def test_v34b_collector_resumes_completed_streams_after_failure(tmp_path: Path) -> None:
    client = FakePublicClient(fail_stream="mark_price:BTC-USDT-SWAP")
    collector = OkxOfficialV1ForwardCollector(
        warehouse_root=tmp_path,
        client=client,
        instruments=("BTC-USDT-SWAP",),
        observed_at="2026-07-19T02:00:00+00:00",
    )

    with pytest.raises(RuntimeError, match="planned_mark_price"):
        collector.run()
    calls_before_resume = list(client.calls)
    result = collector.run()

    assert result["status"] == "completed"
    assert client.calls.count("instrument_metadata") == 1
    assert client.calls.count("open_interest:BTC-USDT-SWAP") == 1
    assert client.calls.count("mark_price:BTC-USDT-SWAP") == 2
    assert len(client.calls) > len(calls_before_resume)


def test_v34b_verifies_the_registered_v34a_snapshot_remains_byte_identical(
    tmp_path: Path,
) -> None:
    root = tmp_path / "okx_official_v1"
    partition = root / "canonical" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "1h" / "part.parquet"
    partition.parent.mkdir(parents=True)
    partition.write_bytes(b"frozen-partition")
    metadata = root / "metadata_snapshots" / "v34a.json"
    metadata.parent.mkdir(parents=True)
    metadata.write_bytes(b'{"frozen":true}\n')
    snapshot_id = "okx_official_v1_snapshot_test"
    snapshot = root / "manifests" / f"snapshot-{snapshot_id}.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text(
        json.dumps(
            {
                "schemaVersion": "okx_official_v1_snapshot_v1",
                "snapshotId": snapshot_id,
                "instrumentMetadataPath": str(metadata),
                "partitions": [
                    {
                        "instrumentId": "BTC-USDT-SWAP",
                        "timeframe": "1h",
                        "outputPath": str(partition),
                        "outputSha256": sha256_file(partition),
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    result = OkxOfficialV1ForwardCollector(
        warehouse_root=tmp_path,
        client=FakePublicClient(),
        instruments=("BTC-USDT-SWAP",),
        observed_at="2026-07-19T03:00:00+00:00",
        base_snapshot_id=snapshot_id,
    ).run()

    assert result["baseSnapshotId"] == snapshot_id
    assert result["baseSnapshotUnchanged"] is True
    assert result["baseSnapshotArtifactCount"] == 3
