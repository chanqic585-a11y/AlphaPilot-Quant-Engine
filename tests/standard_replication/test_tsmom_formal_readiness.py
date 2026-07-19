from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.standard_replication.tsmom_formal_readiness import (
    build_tsmom_formal_readiness,
    write_tsmom_formal_readiness_artifacts,
)


SYMBOLS = ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")


def _write_snapshot(
    root: Path,
    *,
    timeframe: str,
    periods: int,
    start: str = "2025-01-01T00:00:00Z",
) -> Path:
    frequency = {"4h": "4h", "1dutc": "1D"}[timeframe]
    dates = pd.date_range(start, periods=periods, freq=frequency, tz="UTC")
    partitions = []
    for symbol in SYMBOLS:
        frame = pd.DataFrame(
            {
                "date": dates,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1_000.0,
                "confirmed": 1,
            }
        )
        path = root / "ohlcv" / symbol / timeframe / "fixture.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
        partitions.append(
            {
                "instrumentId": symbol,
                "timeframe": timeframe,
                "outputPath": str(path),
                "outputSha256": sha256_file(path),
            }
        )
    manifest = root / "snapshot.json"
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": "fixture_snapshot_v1",
                "snapshotId": "fixture",
                "status": "completed",
                "partitions": partitions,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest


def _write_funding(
    root: Path,
    *,
    start: str,
    end: str,
    endpoint: str = "https://openapi.okx.com/api/v5/public/funding-rate-history",
) -> None:
    dates = pd.date_range(start, end, freq="8h", tz="UTC")
    for symbol in SYMBOLS:
        path = root / symbol / "fixture.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "instrument_id": symbol,
                "funding_rate": 0.0001,
                "timestamp_ms": dates.as_unit("ms").astype("int64"),
                "source_endpoint": endpoint,
                "collected_at": "2026-07-19T00:00:00Z",
            }
        ).to_parquet(path, index=False)


def test_ready_only_with_complete_same_exchange_funding_and_fold_capacity(
    tmp_path: Path,
) -> None:
    snapshot = _write_snapshot(tmp_path, timeframe="4h", periods=1_200)
    funding_root = tmp_path / "funding"
    _write_funding(
        funding_root,
        start="2025-01-01T00:00:00Z",
        end="2025-07-20T00:00:00Z",
    )

    result = build_tsmom_formal_readiness(
        snapshot_manifest_path=snapshot,
        funding_root=funding_root,
        candidate_ids=["v35_tsmom_crypto_adaptation"],
        formal_start="2025-01-01T00:00:00Z",
    )

    assert result["status"] == "ready"
    assert result["formalReadyCandidateCount"] == 1
    assert result["candidates"][0]["blockers"] == []
    assert result["candidates"][0]["fundingCoverage"]["fullWindowCovered"] is True
    assert result["formalRunCount"] == 0
    assert result["formalInputReadCount"] == 0
    assert result["resultReadCount"] == 0
    assert result["lockedOosAccessCount"] == 0
    assert result["releaseCount"] == 0


def test_late_funding_blocks_formal_without_zero_fill(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path, timeframe="4h", periods=1_200)
    funding_root = tmp_path / "funding"
    _write_funding(
        funding_root,
        start="2025-06-01T00:00:00Z",
        end="2025-07-20T00:00:00Z",
    )

    result = build_tsmom_formal_readiness(
        snapshot_manifest_path=snapshot,
        funding_root=funding_root,
        candidate_ids=["v35_tsmom_crypto_adaptation"],
        formal_start="2025-01-01T00:00:00Z",
    )

    candidate = result["candidates"][0]
    assert result["status"] == "blocked"
    assert "funding_window_incomplete" in candidate["blockers"]
    assert candidate["fundingCoverage"]["zeroFilled"] is False
    assert candidate["fundingCoverage"]["fullWindowCovered"] is False


def test_missing_funding_and_short_daily_window_are_separate_blockers(
    tmp_path: Path,
) -> None:
    snapshot = _write_snapshot(tmp_path, timeframe="1dutc", periods=560)

    result = build_tsmom_formal_readiness(
        snapshot_manifest_path=snapshot,
        funding_root=tmp_path / "missing-funding",
        candidate_ids=["v35_tsmom_source_replication"],
        formal_start="2025-01-01T00:00:00Z",
    )

    blockers = result["candidates"][0]["blockers"]
    assert "funding_evidence_missing" in blockers
    assert "purged_walk_forward_capacity_insufficient" in blockers


def test_non_okx_funding_provenance_is_rejected(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path, timeframe="4h", periods=1_200)
    funding_root = tmp_path / "funding"
    _write_funding(
        funding_root,
        start="2025-01-01T00:00:00Z",
        end="2025-07-20T00:00:00Z",
        endpoint="local://user-approved-history",
    )

    result = build_tsmom_formal_readiness(
        snapshot_manifest_path=snapshot,
        funding_root=funding_root,
        candidate_ids=["v35_tsmom_crypto_adaptation"],
        formal_start="2025-01-01T00:00:00Z",
    )

    assert "funding_provenance_invalid" in result["candidates"][0]["blockers"]


def test_writes_auditable_json_markdown_and_manifest(tmp_path: Path) -> None:
    snapshot = _write_snapshot(tmp_path, timeframe="4h", periods=1_200)
    result = build_tsmom_formal_readiness(
        snapshot_manifest_path=snapshot,
        funding_root=tmp_path / "missing-funding",
        candidate_ids=["v35_tsmom_crypto_adaptation"],
        formal_start="2025-01-01T00:00:00Z",
        generated_at="2026-07-19T00:00:00+00:00",
    )

    written = write_tsmom_formal_readiness_artifacts(
        result, output_dir=tmp_path / "reports"
    )

    assert set(written) == {
        "funding_data_readiness.json",
        "funding_data_readiness.md",
        "formal_preflight.json",
        "artifact_manifest.json",
    }
    persisted = json.loads(written["funding_data_readiness.json"].read_text())
    manifest = json.loads(written["artifact_manifest.json"].read_text())
    preflight = json.loads(written["formal_preflight.json"].read_text())
    markdown = written["funding_data_readiness.md"].read_text(encoding="utf-8")
    assert persisted["status"] == "blocked"
    assert manifest["status"] == "blocked"
    assert manifest["formalRunCount"] == 0
    assert preflight["allowedToCreatePreregistration"] is False
    assert preflight["allowedToRunFormal"] is False
    assert "funding_evidence_missing" in markdown
    assert "Formal input reads | 0" in markdown
