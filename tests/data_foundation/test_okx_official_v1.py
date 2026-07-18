from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alphapilot.data_foundation.okx_official_v1 import (
    BAR_DURATION_MS,
    OKX_BAR_VALUES,
    ExistingOkxPartitionAuditor,
    OkxOfficialV1Pilot,
    OkxOfficialV1Layout,
    parse_confirmed_candle_rows,
)
from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.data_foundation.okx_public import OkxHistoryCollectionStopped


def _write_legacy_partition(
    root: Path,
    *,
    instrument_id: str,
    timeframe: str,
    timestamps: list[int],
) -> Path:
    canonical = (
        root
        / "_alphapilot"
        / "canonical"
        / "okx"
        / "swap"
        / "ohlcv"
        / instrument_id
        / timeframe
        / "history.parquet"
    )
    canonical.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "timestamp_ms": timestamps,
            "date": pd.to_datetime(timestamps, unit="ms", utc=True),
            "open": [100.0] * len(timestamps),
            "high": [101.0] * len(timestamps),
            "low": [99.0] * len(timestamps),
            "close": [100.5] * len(timestamps),
            "volume": [1_000.0] * len(timestamps),
            "confirmed": [1] * len(timestamps),
        }
    )
    frame.to_parquet(canonical, index=False)
    digest = sha256_file(canonical)
    manifest = (
        root
        / "_alphapilot"
        / "official"
        / "okx"
        / "raw"
        / "manifests"
        / f"{instrument_id}-{timeframe}-{digest[:16]}.json"
    )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": "okx_official_partition_manifest_v1",
                "instrumentId": instrument_id,
                "timeframe": timeframe,
                "sourceEndpoint": (
                    "https://openapi.okx.com/api/v5/market/history-candles"
                ),
                "requestParameters": {
                    "instId": instrument_id,
                    "bar": timeframe,
                    "confirmedOnly": True,
                },
                "rows": len(frame),
                "startTime": frame["date"].min().isoformat(),
                "endTime": frame["date"].max().isoformat(),
                "outputPath": str(canonical),
                "outputSha256": digest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return canonical


def test_okx_utc_day_and_interval_contract_is_explicit() -> None:
    assert OKX_BAR_VALUES == {"1h": "1H", "4h": "4H", "1dutc": "1Dutc"}
    assert BAR_DURATION_MS["1dutc"] == 24 * 60 * 60 * 1000


def test_confirmed_candle_parser_preserves_all_okx_volume_semantics() -> None:
    ingested_at = "2026-07-19T08:15:00+00:00"
    frame = parse_confirmed_candle_rows(
        [
            [
                "1767225600000",
                "100",
                "110",
                "90",
                "105",
                "12.5",
                "13.5",
                "1400.5",
                "1",
            ]
        ],
        timeframe="1h",
        ingested_at=ingested_at,
    )

    assert frame.loc[0, "vol"] == 12.5
    assert frame.loc[0, "volCcy"] == 13.5
    assert frame.loc[0, "volCcyQuote"] == 1400.5
    assert frame.loc[0, "confirm"] == 1
    assert frame.loc[0, "availableAt"] == "2026-01-01T01:00:00+00:00"
    assert frame.loc[0, "ingestedAt"] == ingested_at


def test_candle_parser_fails_closed_on_schema_drift_and_unconfirmed_rows() -> None:
    try:
        parse_confirmed_candle_rows(
            [["1", "2", "3"]], timeframe="1h", ingested_at="2026-01-01Z"
        )
    except ValueError as error:
        assert str(error) == "okx_history_candle_schema_drift:expected_9_fields:got_3"
    else:
        raise AssertionError("schema drift must fail closed")

    frame = parse_confirmed_candle_rows(
        [["0", "1", "2", "0.5", "1.5", "3", "4", "5", "0"]],
        timeframe="1h",
        ingested_at="2026-01-01T00:00:00+00:00",
    )
    assert frame.empty


def test_existing_audit_reuses_1h_but_never_relabels_1d_as_1dutc(
    tmp_path: Path,
) -> None:
    one_hour = 60 * 60 * 1000
    _write_legacy_partition(
        tmp_path,
        instrument_id="BTC-USDT-SWAP",
        timeframe="1h",
        timestamps=[0, one_hour, 2 * one_hour],
    )
    _write_legacy_partition(
        tmp_path,
        instrument_id="BTC-USDT-SWAP",
        timeframe="1d",
        timestamps=[16 * one_hour, 40 * one_hour],
    )

    audit = ExistingOkxPartitionAuditor(tmp_path).audit(
        instrument_id="BTC-USDT-SWAP",
        timeframe="1h",
    )
    assert audit.classification == "verified_existing_okx"
    assert audit.rows == 3
    assert audit.latestTimestampMs == 2 * one_hour

    utc_day = ExistingOkxPartitionAuditor(tmp_path).audit(
        instrument_id="BTC-USDT-SWAP",
        timeframe="1dutc",
    )
    assert utc_day.classification == "missing_official_partition"
    assert utc_day.incompatibleExistingCount == 1
    assert utc_day.reason == "legacy_1d_is_not_1dutc"


def test_layout_is_bounded_to_the_user_approved_warehouse(tmp_path: Path) -> None:
    layout = OkxOfficialV1Layout.from_warehouse(tmp_path)
    layout.ensure_directories()

    assert layout.root == (tmp_path / "okx_official_v1").resolve()
    assert layout.canonicalRoot.is_dir()
    assert layout.auditRoot.is_dir()
    assert layout.quarantineRoot.is_dir()


class _FakePilotClient:
    base_url = "https://openapi.okx.com"

    def __init__(self, rows: list[list[str]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, object]] = []

    def public_instruments(self, *, instrument_type: str = "SWAP"):
        assert instrument_type == "SWAP"
        return [
            {
                "instId": "BTC-USDT-SWAP",
                "instType": "SWAP",
                "settleCcy": "USDT",
                "state": "live",
                "listTime": "0",
                "tickSz": "0.1",
                "lotSz": "0.001",
                "ctVal": "0.01",
            }
        ]

    def history_candle_rows(self, **kwargs):
        self.calls.append(dict(kwargs))
        progress = kwargs.get("page_progress")
        if progress:
            progress(
                {
                    "requestCount": 1,
                    "rowCount": len(self.rows),
                    "oldestTimestampMs": (
                        min(int(row[0]) for row in self.rows) if self.rows else None
                    ),
                    "maxPages": kwargs["max_pages"],
                    "isFinalPage": True,
                    "pageRows": self.rows,
                }
            )
        return list(self.rows), 1


def test_pilot_reuses_verified_history_and_downloads_only_the_tail(
    tmp_path: Path,
) -> None:
    one_hour = BAR_DURATION_MS["1h"]
    _write_legacy_partition(
        tmp_path,
        instrument_id="BTC-USDT-SWAP",
        timeframe="1h",
        timestamps=[0, one_hour, 2 * one_hour],
    )
    tail_timestamp = 3 * one_hour
    client = _FakePilotClient(
        [
            [
                str(tail_timestamp),
                "100",
                "110",
                "90",
                "105",
                "12.5",
                "13.5",
                "1400.5",
                "1",
            ]
        ]
    )

    result = OkxOfficialV1Pilot(
        warehouse_root=tmp_path,
        client=client,
        instruments=("BTC-USDT-SWAP",),
        timeframes=("1h",),
        requested_start_ms=0,
    ).run()

    assert result["status"] == "completed"
    assert result["partitionCount"] == 1
    assert result["reusedPartitionCount"] == 1
    assert result["downloadedRowCount"] == 1
    assert client.calls[0]["start_exclusive_ms"] == 2 * one_hour
    manifest = result["partitions"][0]
    output = Path(manifest["outputPath"])
    frame = pd.read_parquet(output)
    assert frame["timestamp_ms"].tolist() == [0, one_hour, 2 * one_hour, 3 * one_hour]
    assert frame.loc[0, "volCcyQuote"] == 1_000.0
    assert pd.isna(frame.loc[0, "vol"])
    assert frame.loc[3, "vol"] == 12.5
    assert manifest["baseClassification"] == "verified_existing_okx"
    assert Path(result["dataAuditPath"]).is_file()
    assert Path(result["dataManifestPath"]).is_file()
    assert Path(result["snapshotManifestPath"]).is_file()
    catalog = pd.read_parquet(result["catalogPath"])
    assert catalog[["instrumentId", "timeframe"]].to_dict("records") == [
        {"instrumentId": "BTC-USDT-SWAP", "timeframe": "1h"}
    ]
    assert Path(result["gapMatrixPath"]).suffix == ".csv"
    assert Path(result["provenanceMatrixPath"]).suffix == ".csv"
    assert Path(result["qualityMatrixPath"]).suffix == ".csv"
    assert Path(result["requestAuditPath"]).is_file()


def test_pilot_does_not_reuse_local_day_for_utc_day(tmp_path: Path) -> None:
    day = BAR_DURATION_MS["1dutc"]
    _write_legacy_partition(
        tmp_path,
        instrument_id="BTC-USDT-SWAP",
        timeframe="1d",
        timestamps=[16 * 60 * 60 * 1000, 16 * 60 * 60 * 1000 + day],
    )
    client = _FakePilotClient(
        [["0", "1", "2", "0.5", "1.5", "3", "4", "5", "1"]]
    )

    result = OkxOfficialV1Pilot(
        warehouse_root=tmp_path,
        client=client,
        instruments=("BTC-USDT-SWAP",),
        timeframes=("1dutc",),
        requested_start_ms=0,
    ).run()

    assert result["reusedPartitionCount"] == 0
    assert client.calls[0]["start_exclusive_ms"] == 0
    partition = result["partitions"][0]
    assert partition["baseClassification"] == "missing_official_partition"
    assert partition["incompatibleExistingCount"] == 1
    frame = pd.read_parquet(partition["outputPath"])
    assert frame["timestamp_ms"].tolist() == [0]


class _InterruptingPilotClient(_FakePilotClient):
    def history_candle_rows(self, **kwargs):
        self.calls.append(dict(kwargs))
        row = self.rows[0]
        kwargs["page_progress"](
            {
                "requestCount": 1,
                "rowCount": 1,
                "oldestTimestampMs": int(row[0]),
                "maxPages": kwargs["max_pages"],
                "isFinalPage": False,
                "pageRows": [row],
            }
        )
        raise OkxHistoryCollectionStopped("test_pause")


def test_pilot_resumes_from_durable_page_rows(tmp_path: Path) -> None:
    one_hour = BAR_DURATION_MS["1h"]
    first = _InterruptingPilotClient(
        [[str(2 * one_hour), "1", "2", "0.5", "1.5", "3", "4", "5", "1"]]
    )
    pilot = OkxOfficialV1Pilot(
        warehouse_root=tmp_path,
        client=first,
        instruments=("BTC-USDT-SWAP",),
        timeframes=("1h",),
        requested_start_ms=0,
    )
    try:
        pilot.run()
    except OkxHistoryCollectionStopped:
        pass
    else:
        raise AssertionError("the first run must stop after persisting its page")

    second = _FakePilotClient(
        [[str(one_hour), "1", "2", "0.5", "1.5", "6", "7", "8", "1"]]
    )
    result = OkxOfficialV1Pilot(
        warehouse_root=tmp_path,
        client=second,
        instruments=("BTC-USDT-SWAP",),
        timeframes=("1h",),
        requested_start_ms=0,
    ).run()

    assert second.calls[0]["initial_after_ms"] == 2 * one_hour
    frame = pd.read_parquet(result["partitions"][0]["outputPath"])
    assert frame["timestamp_ms"].tolist() == [one_hour, 2 * one_hour]
    checkpoint = (
        OkxOfficialV1Layout.from_warehouse(tmp_path).checkpointRoot
        / "BTC-USDT-SWAP-1h.json"
    )
    assert not checkpoint.exists()


def test_identical_pilot_rerun_preserves_immutable_snapshot_identity(
    tmp_path: Path,
) -> None:
    one_hour = BAR_DURATION_MS["1h"]
    first = OkxOfficialV1Pilot(
        warehouse_root=tmp_path,
        client=_FakePilotClient(
            [[str(one_hour), "1", "2", "0.5", "1.5", "3", "4", "5", "1"]]
        ),
        instruments=("BTC-USDT-SWAP",),
        timeframes=("1h",),
        requested_start_ms=0,
    ).run()
    metadata_path = next(
        OkxOfficialV1Layout.from_warehouse(tmp_path).metadataSnapshotRoot.glob(
            "instruments-*.json"
        )
    )
    first_metadata_hash = sha256_file(metadata_path)
    first_snapshot_hash = sha256_file(first["snapshotManifestPath"])

    second = OkxOfficialV1Pilot(
        warehouse_root=tmp_path,
        client=_FakePilotClient([]),
        instruments=("BTC-USDT-SWAP",),
        timeframes=("1h",),
        requested_start_ms=0,
    ).run()

    assert second["snapshotId"] == first["snapshotId"]
    assert second["partitions"][0]["outputPath"] == first["partitions"][0]["outputPath"]
    assert sha256_file(metadata_path) == first_metadata_hash
    assert sha256_file(second["snapshotManifestPath"]) == first_snapshot_hash
