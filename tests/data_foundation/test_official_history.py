from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from alphapilot.data_foundation.official_history import OkxOfficialHistoryCollector
from alphapilot.data_foundation.okx_public import OkxHistoryCollectionStopped
from alphapilot.data_foundation.warehouse import WarehouseLayout
from alphapilot.evolution.workflow.types import StrategyDataContractRecord


def _contract() -> StrategyDataContractRecord:
    payload = {
        "schemaVersion": "strategy_data_contract_v1",
        "strategyVersionId": "strategy_version_official_test",
        "strategyContentHash": "strategy_hash_official_test",
        "marketType": "swap",
        "direction": "both",
        "signalTimeframe": "4h",
        "executionTimeframe": "15m",
        "executionFallbackTimeframe": None,
        "requestedStart": "2020-01-01T00:00:00+00:00",
        "requestedEndPolicy": "latest_completed_at_run",
        "targetR": 2.0,
        "universePolicy": {
            "type": "point_in_time_dynamic_liquid_usdt_swap",
            "minimumMembers": 2,
            "targetMembers": 2,
            "candidateDiscovery": ["okx_public_instruments"],
        },
    }
    return StrategyDataContractRecord(
        strategyDataContractId="strategy_data_contract_official_test",
        strategyVersionId="strategy_version_official_test",
        schemaVersion="strategy_data_contract_v1",
        contract=payload,
        contentHash="strategy_data_contract_official_test",
    )


def _frame(timeframe: str) -> pd.DataFrame:
    frequency = {"15m": "15min", "4h": "4h"}[timeframe]
    timestamps = pd.date_range("2026-01-01", periods=240, freq=frequency, tz="UTC")
    return pd.DataFrame(
        {
            "timestamp_ms": timestamps.as_unit("ms").astype("int64"),
            "date": timestamps,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1000.0,
            "confirmed": 1,
        }
    )


class FakeOkxClient:
    base_url = "https://official.example"

    def __init__(self, *, invalid: bool = False) -> None:
        self.invalid = invalid
        self.history_calls: list[tuple[str, str]] = []

    def public_instruments(self, *, instrument_type: str = "SWAP"):
        if instrument_type != "SWAP":
            raise AssertionError(instrument_type)
        return [
            {
                "instId": "BTC-USDT-SWAP",
                "instType": "SWAP",
                "settleCcy": "USDT",
                "state": "live",
                "listTime": "1577836800000",
            },
            {
                "instId": "ETH-USDT-SWAP",
                "instType": "SWAP",
                "settleCcy": "USDT",
                "state": "live",
                "listTime": "1577836800000",
            },
        ]

    def history_candles(self, *, instrument_id: str, timeframe: str, **_kwargs):
        self.history_calls.append((instrument_id, timeframe))
        frame = _frame(timeframe)
        if self.invalid:
            frame.loc[0, "low"] = 102.0
        return frame, 3

    def funding_rate_history(self, *, instrument_id: str, **_kwargs):
        return [
            {
                "instId": instrument_id,
                "fundingRate": "0.0001",
                "fundingTime": "1767225600000",
            }
        ]


class InterruptingOkxClient(FakeOkxClient):
    def history_candles(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        stop_requested=None,
        **_kwargs,
    ):
        self.history_calls.append((instrument_id, timeframe))
        if stop_requested is None:
            raise AssertionError("collector_did_not_forward_stop_callback")
        raise OkxHistoryCollectionStopped("official_history_collection_stopped")


class OfficialHistoryCollectorTests(unittest.TestCase):
    def test_collects_strategy_first_official_partitions_and_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layout = WarehouseLayout.from_root(Path(directory) / "回测数据")
            client = FakeOkxClient()
            collector = OkxOfficialHistoryCollector(client=client, layout=layout)

            first = collector.collect(_contract())
            first_call_count = len(client.history_calls)
            second = collector.collect(_contract())

            self.assertEqual(first.status, "completed")
            self.assertEqual(first.instrumentCount, 2)
            self.assertEqual(first.completedPartitionCount, 4)
            self.assertEqual(first.failedPartitionCount, 0)
            self.assertEqual(first_call_count, 4)
            self.assertEqual(len(client.history_calls), first_call_count)
            self.assertEqual(second.reusedPartitionCount, 4)
            self.assertTrue(all(Path(item.outputPath).is_file() for item in first.partitions))
            self.assertTrue(all(item.provenanceStatus == "official_okx_public" for item in first.partitions))
            self.assertTrue(all(item.sourceEndpoint.endswith("/api/v5/market/history-candles") for item in first.partitions))

    def test_pause_marker_stops_before_first_partition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layout = WarehouseLayout.from_root(Path(directory) / "回测数据")
            layout.ensure_directories()
            pause = layout.checkpointRoot / "PAUSE_REQUESTED"
            pause.write_text("pause", encoding="utf-8")
            client = FakeOkxClient()

            result = OkxOfficialHistoryCollector(
                client=client, layout=layout, pause_file=pause
            ).collect(_contract())

            self.assertEqual(result.status, "paused")
            self.assertEqual(result.completedPartitionCount, 0)
            self.assertEqual(client.history_calls, [])

    def test_page_level_stop_returns_paused_without_partial_partition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layout = WarehouseLayout.from_root(Path(directory) / "回测数据")
            client = InterruptingOkxClient()

            self.assertIn(
                "stop_requested",
                inspect.signature(OkxOfficialHistoryCollector).parameters,
            )

            result = OkxOfficialHistoryCollector(
                client=client,
                layout=layout,
                stop_requested=lambda: False,
            ).collect(_contract())

            self.assertEqual(result.status, "paused")
            self.assertEqual(result.completedPartitionCount, 0)
            self.assertEqual(result.failedPartitionCount, 0)
            self.assertEqual(result.partitions, ())
            self.assertEqual(client.history_calls, [("BTC-USDT-SWAP", "15m")])

    def test_invalid_ohlc_partition_is_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layout = WarehouseLayout.from_root(Path(directory) / "回测数据")
            result = OkxOfficialHistoryCollector(
                client=FakeOkxClient(invalid=True), layout=layout
            ).collect(_contract())

            self.assertEqual(result.status, "blocked")
            self.assertEqual(result.completedPartitionCount, 0)
            self.assertEqual(result.failedPartitionCount, 4)
            self.assertTrue(all(item.status == "quarantined" for item in result.partitions))
            self.assertTrue(all(not item.outputPath for item in result.partitions))


if __name__ == "__main__":
    unittest.main()
