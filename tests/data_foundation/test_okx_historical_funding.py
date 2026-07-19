from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from alphapilot.data_foundation.okx_historical_funding import (
    HistoricalFundingArchiveError,
    OkxHistoricalFundingBackfill,
    parse_historical_funding_archive,
)


INSTRUMENT = "BTC-USDT-SWAP"
SOURCE_URL = (
    "https://static.okx.com/cdn/okex/traderecords/swaprates/monthly/"
    "202501/BTC-USDT-SWAP-fundingrates-2025-01.zip?v=999"
)


def _archive_bytes(*, instrument: str = INSTRUMENT) -> bytes:
    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{instrument}-fundingrates-2025-01.csv",
            "instrument_name,funding_rate,funding_time\n"
            f"{instrument},0.0001,1735660800000\n"
            f"{instrument},-0.0002,1735689600000\n",
        )
    return stream.getvalue()


def _index_payload() -> list[dict[str, object]]:
    return [
        {
            "dateAggrType": "monthly",
            "details": [
                {
                    "instFamily": "BTC-USDT",
                    "instType": "SWAP",
                    "groupDetails": [
                        {
                            "dateTs": "1735689600000",
                            "filename": "BTC-USDT-SWAP-fundingrates-2025-01.zip",
                            "sizeMB": "0",
                            "url": SOURCE_URL,
                        }
                    ],
                }
            ],
        }
    ]


class _FakeHistoricalClient:
    base_url = "https://openapi.okx.com"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def historical_market_data(self, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(dict(kwargs))
        return _index_payload()

    def funding_rate_history(self, **_: object) -> list[dict[str, str]]:
        return [
            {
                "instId": INSTRUMENT,
                "fundingRate": "0.0003",
                "fundingTime": "1738368000000",
            }
        ]


def test_parse_historical_funding_archive_normalizes_official_schema() -> None:
    frame = parse_historical_funding_archive(
        _archive_bytes(),
        instrument_id=INSTRUMENT,
        source_url=SOURCE_URL,
        retrieved_at="2026-07-19T00:00:00Z",
    )

    assert list(frame["instrument_id"].unique()) == [INSTRUMENT]
    assert list(frame["funding_rate"]) == [0.0001, -0.0002]
    assert list(frame["timestamp_ms"]) == [1735660800000, 1735689600000]
    assert set(frame["source_endpoint"]) == {SOURCE_URL}
    assert frame["archive_sha256"].str.fullmatch(r"[0-9a-f]{64}").all()
    assert frame["available_at"].tolist() == [
        "2024-12-31T16:00:00+00:00",
        "2025-01-01T00:00:00+00:00",
    ]


def test_parse_historical_funding_archive_rejects_wrong_instrument() -> None:
    with pytest.raises(
        HistoricalFundingArchiveError,
        match="funding_archive_instrument_mismatch",
    ):
        parse_historical_funding_archive(
            _archive_bytes(instrument="ETH-USDT-SWAP"),
            instrument_id=INSTRUMENT,
            source_url=SOURCE_URL,
            retrieved_at="2026-07-19T00:00:00Z",
        )


def test_backfill_writes_raw_canonical_manifest_and_resumes(tmp_path: Path) -> None:
    client = _FakeHistoricalClient()
    download_calls: list[str] = []

    def download(url: str) -> bytes:
        download_calls.append(url)
        return _archive_bytes()

    backfill = OkxHistoricalFundingBackfill(
        warehouse_root=tmp_path,
        client=client,
        archive_loader=download,
        instruments=(INSTRUMENT,),
        begin="2025-01-01T00:00:00Z",
        end="2025-01-31T00:00:00Z",
        observed_at="2026-07-19T00:00:00Z",
    )

    first = backfill.run()
    second = backfill.run()

    assert first["status"] == "completed"
    assert first["archiveCount"] == 1
    assert first["completedArchiveCount"] == 1
    assert first["downloadedArchiveCount"] == 1
    assert second["completedArchiveCount"] == 1
    assert second["downloadedArchiveCount"] == 0
    assert download_calls == [SOURCE_URL]
    assert client.calls[0] == {
        "module": 3,
        "instrument_type": "SWAP",
        "instrument_family_list": ("BTC-USDT",),
        "date_aggregation_type": "monthly",
        "begin_ms": 1735689600000,
        "end_ms": 1738281600000,
    }

    canonical = Path(first["artifacts"][0]["canonicalPath"])
    raw = Path(first["artifacts"][0]["rawPath"])
    manifest = Path(first["manifestPath"])
    checkpoint = Path(first["checkpointPath"])
    assert canonical.is_file()
    assert raw.is_file()
    assert manifest.is_file()
    assert checkpoint.is_file()
    assert len(pd.read_parquet(canonical)) == 2
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["status"] == "completed"
    persisted = json.loads(manifest.read_text(encoding="utf-8"))
    assert persisted["publicDataOnly"] is True
    assert persisted["zeroFillUsed"] is False
    assert persisted["mixedExchangeFundingUsed"] is False


def test_backfill_splits_archive_discovery_into_at_most_twenty_month_windows(
    tmp_path: Path,
) -> None:
    client = _FakeHistoricalClient()
    backfill = OkxHistoricalFundingBackfill(
        warehouse_root=tmp_path,
        client=client,
        archive_loader=lambda _: _archive_bytes(),
        instruments=(INSTRUMENT,),
        begin="2022-03-01T00:00:00Z",
        end="2026-07-19T00:00:00Z",
        observed_at="2026-07-19T00:00:00Z",
    )

    backfill._discover(INSTRUMENT)

    assert len(client.calls) == 3
    first, second, third = client.calls
    assert first["begin_ms"] == 1646092800000
    assert first["end_ms"] < second["begin_ms"]
    assert second["end_ms"] < third["begin_ms"]
    assert third["end_ms"] == 1784419200000
    for call in client.calls:
        begin = pd.Timestamp(int(call["begin_ms"]), unit="ms", tz="UTC")
        end = pd.Timestamp(int(call["end_ms"]), unit="ms", tz="UTC")
        assert end <= begin + pd.DateOffset(months=20)


def test_backfill_can_append_recent_public_funding_tail(tmp_path: Path) -> None:
    backfill = OkxHistoricalFundingBackfill(
        warehouse_root=tmp_path,
        client=_FakeHistoricalClient(),
        archive_loader=lambda _: _archive_bytes(),
        instruments=(INSTRUMENT,),
        begin="2025-01-01T00:00:00Z",
        end="2025-01-31T00:00:00Z",
        observed_at="2026-07-19T00:00:00Z",
        include_recent_tail=True,
    )

    result = backfill.run()

    assert result["recentTailRowCount"] == 1
    tail = next(
        artifact
        for artifact in result["artifacts"]
        if artifact["artifactType"] == "recentFundingTail"
    )
    frame = pd.read_parquet(Path(tail["canonicalPath"]))
    assert frame.iloc[0]["timestamp_ms"] == 1738368000000
    assert frame.iloc[0]["source_endpoint"].endswith(
        "/api/v5/public/funding-rate-history"
    )
