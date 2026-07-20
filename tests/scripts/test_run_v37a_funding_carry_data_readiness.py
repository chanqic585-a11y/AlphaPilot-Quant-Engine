from __future__ import annotations

import json
from pathlib import Path
import re

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.scripts.run_v37a_funding_carry_data_readiness import run


def _write_manifested_partition(
    *,
    warehouse: Path,
    instrument_id: str,
    kind: str,
    frame: pd.DataFrame,
) -> None:
    if kind == "perpetual":
        output = warehouse / "okx_official_v1" / "canonical" / "swap" / "ohlcv" / instrument_id / "1h" / "fixture.parquet"
        manifest = warehouse / "okx_official_v1" / "manifests" / f"{instrument_id}-1h-fixture.json"
        schema = "okx_official_v1_partition_manifest_v1"
        source = "https://openapi.okx.com/api/v5/market/history-candles"
    elif kind == "spot":
        output = warehouse / "okx_official_v1" / "funding_carry_v37a" / "canonical" / "spot" / "ohlcv" / instrument_id / "1h" / "fixture.parquet"
        manifest = warehouse / "okx_official_v1" / "funding_carry_v37a" / "manifests" / "spot" / f"{instrument_id}-1h-fixture.json"
        schema = "v37a_okx_spot_partition_manifest_v1"
        source = "https://openapi.okx.com/api/v5/market/history-candles"
    else:
        output = warehouse / "okx_official_v1" / "funding_carry_v37a" / "canonical" / "funding" / instrument_id / "fixture.parquet"
        manifest = warehouse / "okx_official_v1" / "funding_carry_v37a" / "manifests" / "funding" / f"{instrument_id}-fixture.json"
        schema = "v37a_okx_funding_partition_manifest_v1"
        source = "verified_v36_monthly_plus_v34b_recent"
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": schema,
                "instrumentId": instrument_id,
                "timeframe": "funding" if kind == "funding" else "1h",
                "sourceEndpoint": source,
                "outputPath": str(output.resolve()),
                "outputSha256": sha256_file(output),
                "sources": [] if kind == "funding" else None,
            }
        ),
        encoding="utf-8",
    )


def _candle_frame(instrument_id: str, prices: tuple[float, float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp_ms": [25_200_000, 54_000_000],
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "vol": [10.0, 10.0],
            "volCcy": [10.0, 10.0],
            "volCcyQuote": [10_000.0, 12_000.0],
            "confirm": [1, 1],
            "availableAt": [
                "1970-01-01T08:00:00+00:00",
                "1970-01-01T16:00:00+00:00",
            ],
            "ingestedAt": ["2026-07-19T00:00:00+00:00"] * 2,
        }
    )


def test_audit_cli_writes_data_only_readiness_reports(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse"
    reports = tmp_path / "reports"
    preregistration = tmp_path / "funding-carry.json"
    preregistration.write_text(
        json.dumps(
            {
                "familyId": "crypto_funding_carry_v1",
                "requiredAlignedData": [
                    "same_exchange_spot",
                    "same_exchange_perpetual",
                    "funding_rate",
                    "dual_leg_cost_and_capacity",
                ],
                "executionCandidateCount": 0,
                "lockedOosReadCount": 0,
                "releaseCount": 0,
                "demoArm": False,
                "orderCount": 0,
            }
        ),
        encoding="utf-8",
    )
    _write_manifested_partition(
        warehouse=warehouse,
        instrument_id="BTC-USDT-SWAP",
        kind="perpetual",
        frame=_candle_frame("BTC-USDT-SWAP", (101.0, 102.0)),
    )
    _write_manifested_partition(
        warehouse=warehouse,
        instrument_id="BTC-USDT",
        kind="spot",
        frame=_candle_frame("BTC-USDT", (100.0, 100.0)),
    )
    _write_manifested_partition(
        warehouse=warehouse,
        instrument_id="BTC-USDT-SWAP",
        kind="funding",
        frame=pd.DataFrame(
            {
                "instrument_id": ["BTC-USDT-SWAP", "BTC-USDT-SWAP"],
                "timestamp_ms": [28_800_000, 57_600_000],
                "available_at": [
                    "1970-01-01T08:00:00+00:00",
                    "1970-01-01T16:00:00+00:00",
                ],
                "funding_rate": [0.0001, -0.0001],
            }
        ),
    )

    result = run(
        [
            "--warehouse-root",
            str(warehouse),
            "--report-root",
            str(reports),
            "--preregistration-path",
            str(preregistration),
            "--asset",
            "BTC",
            "--begin",
            "1970-01-01T00:00:00+00:00",
            "--end",
            "1970-01-02T00:00:00+00:00",
            "--observed-at",
            "2026-07-19T00:00:00+00:00",
            "--minimum-aligned-rows",
            "2",
            "--minimum-coverage-days",
            "0",
        ]
    )

    assert result["status"] == "completed"
    output = Path(result["reportDirectory"])
    assert re.fullmatch(r"v37a-funding-carry-[0-9a-f]{20}", output.name)
    expected = {
        "funding_carry_data_readiness.json",
        "funding_carry_data_readiness.md",
        "coverage_matrix.csv",
        "cost_capacity_evidence.json",
        "artifact_manifest.json",
        "request_audit.json",
    }
    assert expected.issubset({path.name for path in output.iterdir()})
    readiness = json.loads(
        (output / "funding_carry_data_readiness.json").read_text(encoding="utf-8")
    )
    assert readiness["historicalResearchReady"] is True
    assert readiness["formalResearchDataReady"] is True
    assert readiness["forwardExecutionEvidenceReady"] is False
    markdown = (output / "funding_carry_data_readiness.md").read_text(
        encoding="utf-8"
    )
    assert "Historical / Formal decision: **READY**" in markdown
    assert "Forward execution evidence: **BLOCKED**" in markdown
    assert readiness["sideEffects"] == {
        "candidateCount": 0,
        "formalRunCount": 0,
        "resultReadCount": 0,
        "releaseCount": 0,
        "demoArmCount": 0,
        "orderCount": 0,
    }
    manifest = json.loads(
        (output / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["preregistrationSha256"] == sha256_file(preregistration)
    assert manifest["dataOnly"] is True
    assert manifest["panelArtifacts"][0]["sha256"]
    assert re.fullmatch(
        r"panel-[0-9a-f]{20}\.parquet",
        Path(manifest["panelArtifacts"][0]["path"]).name,
    )


def test_audit_reports_spot_and_funding_gaps_independently(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse"
    reports = tmp_path / "reports"
    preregistration = tmp_path / "funding-carry.json"
    preregistration.write_text(
        json.dumps(
            {
                "familyId": "crypto_funding_carry_v1",
                "requiredAlignedData": sorted(
                    {
                        "same_exchange_spot",
                        "same_exchange_perpetual",
                        "funding_rate",
                        "dual_leg_cost_and_capacity",
                    }
                ),
                "executionCandidateCount": 0,
                "lockedOosReadCount": 0,
                "releaseCount": 0,
                "demoArm": False,
                "orderCount": 0,
            }
        ),
        encoding="utf-8",
    )
    _write_manifested_partition(
        warehouse=warehouse,
        instrument_id="BTC-USDT-SWAP",
        kind="perpetual",
        frame=_candle_frame("BTC-USDT-SWAP", (101.0, 102.0)),
    )

    result = run(
        [
            "--warehouse-root",
            str(warehouse),
            "--report-root",
            str(reports),
            "--preregistration-path",
            str(preregistration),
            "--asset",
            "BTC",
            "--begin",
            "1970-01-01T00:00:00+00:00",
            "--end",
            "1970-01-02T00:00:00+00:00",
            "--observed-at",
            "2026-07-19T00:00:00+00:00",
            "--minimum-aligned-rows",
            "2",
            "--minimum-coverage-days",
            "0",
        ]
    )

    readiness = json.loads(
        (
            Path(result["reportDirectory"])
            / "funding_carry_data_readiness.json"
        ).read_text(encoding="utf-8")
    )
    blockers = readiness["historicalBlockers"]
    assert any("verified_spot_partition_missing:BTC-USDT:1h" in item for item in blockers)
    assert any(
        "verified_actual_funding_sources_missing:BTC-USDT-SWAP" in item
        for item in blockers
    )
