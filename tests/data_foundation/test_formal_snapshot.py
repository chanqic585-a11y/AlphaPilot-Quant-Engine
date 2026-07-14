from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import pandas as pd

from alphapilot.data_foundation.formal_snapshot import (
    FormalSnapshotError,
    freeze_formal_snapshot,
)
from alphapilot.data_foundation.official_history import (
    OfficialCollectionResult,
    OfficialPartition,
)
from alphapilot.data_foundation.warehouse import WarehouseLayout
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.workflow.types import StrategyDataContractRecord


def make_contract(
    *, minimum_members: int = 2, target_members: int = 2
) -> StrategyDataContractRecord:
    payload = {
        "schemaVersion": "strategy_data_contract_v1",
        "strategyVersionId": "strategy_version_snapshot_test",
        "strategyContentHash": "strategy_hash_snapshot_test",
        "marketType": "swap",
        "direction": "both",
        "signalTimeframe": "4h",
        "executionTimeframe": "15m",
        "executionFallbackTimeframe": None,
        "requestedStart": "2020-01-01T00:00:00+00:00",
        "targetR": 2.0,
        "universePolicy": {
            "minimumMembers": minimum_members,
            "targetMembers": target_members,
        },
        "validationPolicy": {
            "purgedWalkForward": True,
            "unseenSymbolHoldout": True,
            "lockedOos": True,
            "regimeCoverage": [
                "bull",
                "bear",
                "range",
                "crash",
                "volatility_expansion",
            ],
            "sameBarAmbiguity": "stop_first",
        },
        "costPolicy": {
            "feeRate": 0.0005,
            "slippageRate": 0.0002,
            "fundingRequiredForSwap": True,
            "latencyBars": [0, 1, 2],
            "stressMultipliers": [1.0, 1.5, 2.0],
        },
    }
    return StrategyDataContractRecord(
        strategyDataContractId="strategy_data_contract_snapshot_test",
        strategyVersionId="strategy_version_snapshot_test",
        schemaVersion="strategy_data_contract_v1",
        contract=payload,
        contentHash="strategy_data_contract_snapshot_test",
    )


def write_ohlcv(
    layout: WarehouseLayout,
    instrument: str,
    timeframe: str,
    *,
    gap: bool = False,
) -> OfficialPartition:
    interval = {"15m": 15, "4h": 240}[timeframe]
    dates = pd.date_range(
        "2020-01-01", periods=360, freq=f"{interval}min", tz="UTC"
    )
    if gap:
        dates = dates.delete(100)
    close = pd.Series(range(len(dates)), dtype="float64") * 0.05 + 100.0
    frame = pd.DataFrame(
        {
            "timestamp_ms": dates.as_unit("ms").astype("int64"),
            "date": dates,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close + 0.25,
            "volume": 1000.0,
            "confirmed": 1,
            "exchange": "okx",
            "market_type": "swap",
            "instrument_id": instrument,
            "timeframe": timeframe,
            "source_endpoint": "https://www.okx.com/api/v5/market/history-candles",
            "collected_at": "2026-07-11T00:00:00+00:00",
        }
    )
    path = (
        layout.canonicalRoot
        / "okx"
        / "swap"
        / "ohlcv"
        / instrument
        / timeframe
        / "fixture.parquet"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False, compression="zstd")
    return OfficialPartition(
        instrumentId=instrument,
        timeframe=timeframe,
        status="collected",
        rows=len(frame),
        startTime=dates.min().isoformat(),
        endTime=dates.max().isoformat(),
        outputPath=str(path),
        outputSha256=sha256_file(path),
        sourceEndpoint="https://www.okx.com/api/v5/market/history-candles",
        requestCount=4,
        provenanceStatus="official_okx_public",
    )


def write_funding(layout: WarehouseLayout, instrument: str) -> Path:
    path = (
        layout.canonicalRoot
        / "okx"
        / "swap"
        / "funding"
        / instrument
        / "fixture.parquet"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "instrument_id": [instrument],
            "funding_rate": [0.0001],
            "timestamp_ms": [1577836800000],
            "source_endpoint": [
                "https://www.okx.com/api/v5/public/funding-rate-history"
            ],
            "collected_at": ["2026-07-11T00:00:00+00:00"],
        }
    ).to_parquet(path, index=False, compression="zstd")
    return path


def make_collection(
    layout: WarehouseLayout,
    *,
    third_party: bool = False,
    gap: bool = False,
) -> OfficialCollectionResult:
    partitions = [
        write_ohlcv(layout, instrument, timeframe, gap=gap)
        for instrument in ("BTC-USDT-SWAP", "ETH-USDT-SWAP")
        for timeframe in ("15m", "4h")
    ]
    if third_party:
        partitions[0] = replace(
            partitions[0], provenanceStatus="third_party_unverified"
        )
    funding = tuple(
        str(write_funding(layout, instrument))
        for instrument in ("BTC-USDT-SWAP", "ETH-USDT-SWAP")
    )
    return OfficialCollectionResult(
        status="completed",
        strategyDataContractId="strategy_data_contract_snapshot_test",
        instrumentCount=2,
        completedPartitionCount=4,
        reusedPartitionCount=0,
        failedPartitionCount=0,
        fundingFileCount=2,
        partitions=tuple(partitions),
        checkpointPath=str(layout.checkpointRoot / "fixture.json"),
        generatedAt="2026-07-11T00:00:00+00:00",
        fundingPaths=funding,
    )


class FormalSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.layout = WarehouseLayout.from_root(Path(self.temp.name) / "回测数据")
        self.layout.ensure_directories()
        self.connection = connect_registry(Path(self.temp.name) / "registry.sqlite")
        self.repository = RegistryRepository(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def test_freezes_and_registers_only_complete_official_snapshot(self) -> None:
        snapshot = freeze_formal_snapshot(
            make_collection(self.layout),
            make_contract(),
            self.layout,
            self.repository,
        )

        self.assertEqual(snapshot.source, "okx_public_official")
        self.assertEqual(snapshot.exchange, "okx")
        self.assertTrue(snapshot.manifest["metadata"]["provenanceComplete"])

    def test_freezes_user_approved_local_snapshot_without_claiming_official_source(self) -> None:
        collection = make_collection(self.layout)
        local_partitions = []
        for partition in collection.partitions:
            path = Path(str(partition.outputPath))
            frame = pd.read_parquet(path)
            frame["exchange"] = "user_local"
            frame["source_endpoint"] = "local://user-approved-history"
            frame.to_parquet(path, index=False, compression="zstd")
            local_partitions.append(
                replace(
                    partition,
                    outputSha256=sha256_file(path),
                    sourceEndpoint="local://user-approved-history",
                    provenanceStatus="user_approved_local",
                )
            )
        for funding_path in collection.fundingPaths:
            path = Path(funding_path)
            frame = pd.read_parquet(path)
            frame["source_endpoint"] = "local://user-approved-history"
            frame.to_parquet(path, index=False, compression="zstd")
        collection = replace(collection, partitions=tuple(local_partitions))

        snapshot = freeze_formal_snapshot(
            collection,
            make_contract(),
            self.layout,
            self.repository,
        )

        self.assertEqual(snapshot.source, "user_approved_local_market_data")
        self.assertEqual(snapshot.exchange, "user_local")
        self.assertTrue(snapshot.manifest["metadata"]["userApprovedLocalData"])
        self.assertTrue(snapshot.manifest["metadata"]["pointInTimeValidated"])
        self.assertTrue(snapshot.manifest["metadata"]["formalResearchEligible"])
        self.assertTrue(snapshot.manifest["metadata"]["formalPromotionEligible"])
        self.assertEqual(
            snapshot.manifest["metadata"]["evidenceClass"], "formal_backtest"
        )
        self.assertEqual(len(snapshot.manifest["files"]), 6)
        self.assertEqual(
            self.repository.get_data_snapshot(snapshot.dataSnapshotId), snapshot
        )

    def test_third_party_or_gapped_partition_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            FormalSnapshotError, "formal_partition_provenance_invalid"
        ):
            freeze_formal_snapshot(
                make_collection(self.layout, third_party=True),
                make_contract(),
                self.layout,
                self.repository,
            )

        with tempfile.TemporaryDirectory() as second_directory:
            second_layout = WarehouseLayout.from_root(
                Path(second_directory) / "回测数据"
            )
            second_layout.ensure_directories()
            with self.assertRaisesRegex(
                FormalSnapshotError, "formal_partition_gap_detected"
            ):
                freeze_formal_snapshot(
                    make_collection(second_layout, gap=True),
                    make_contract(),
                    second_layout,
                    self.repository,
                )

    def test_excludes_gapped_instrument_when_dynamic_universe_stays_large_enough(
        self,
    ) -> None:
        instruments = ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")
        partitions = tuple(
            write_ohlcv(
                self.layout,
                instrument,
                timeframe,
                gap=instrument == "SOL-USDT-SWAP",
            )
            for instrument in instruments
            for timeframe in ("15m", "4h")
        )
        collection = OfficialCollectionResult(
            status="completed",
            strategyDataContractId="strategy_data_contract_snapshot_test",
            instrumentCount=3,
            completedPartitionCount=6,
            reusedPartitionCount=0,
            failedPartitionCount=0,
            fundingFileCount=3,
            partitions=partitions,
            checkpointPath=str(self.layout.checkpointRoot / "fixture.json"),
            generatedAt="2026-07-11T00:00:00+00:00",
            fundingPaths=tuple(
                str(write_funding(self.layout, instrument))
                for instrument in instruments
            ),
        )

        snapshot = freeze_formal_snapshot(
            collection,
            make_contract(minimum_members=2, target_members=3),
            self.layout,
            self.repository,
        )

        self.assertEqual(
            snapshot.manifest["universeMembers"],
            ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
        )
        self.assertEqual(len(snapshot.manifest["files"]), 6)
        self.assertEqual(
            snapshot.manifest["metadata"]["excludedInstruments"],
            {
                "SOL-USDT-SWAP": (
                    "formal_partition_gap_detected:SOL-USDT-SWAP:15m"
                )
            },
        )


if __name__ == "__main__":
    unittest.main()
