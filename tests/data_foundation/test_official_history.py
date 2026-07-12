from __future__ import annotations

import inspect
import json
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


def _single_partition_contract(contract_id: str) -> StrategyDataContractRecord:
    payload = {
        **_contract().contract,
        "strategyVersionId": f"strategy_version_{contract_id}",
        "signalTimeframe": "15m",
        "executionTimeframe": "15m",
        "universePolicy": {
            "type": "point_in_time_dynamic_liquid_usdt_swap",
            "minimumMembers": 1,
            "targetMembers": 1,
            "candidateDiscovery": ["okx_public_instruments"],
        },
    }
    return StrategyDataContractRecord(
        strategyDataContractId=contract_id,
        strategyVersionId=str(payload["strategyVersionId"]),
        schemaVersion="strategy_data_contract_v1",
        contract=payload,
        contentHash=contract_id,
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


class CheckpointInspectingOkxClient(FakeOkxClient):
    def __init__(self, checkpoint_path: Path) -> None:
        super().__init__()
        self.checkpoint_path = checkpoint_path
        self.progress_snapshots: list[dict[str, object]] = []

    def history_candles(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        page_progress=None,
        **_kwargs,
    ):
        self.history_calls.append((instrument_id, timeframe))
        if page_progress is None:
            raise AssertionError("collector_did_not_forward_page_progress")
        page_progress(
            {
                "requestCount": 1,
                "rowCount": 100,
                "oldestTimestampMs": 1_700_000_000_000,
                "maxPages": 100,
                "isFinalPage": False,
            }
        )
        self.progress_snapshots.append(
            json.loads(self.checkpoint_path.read_text(encoding="utf-8"))["inProgress"]
        )
        return _frame(timeframe), 3


class TailRecordingOkxClient(FakeOkxClient):
    def __init__(self, *, return_tail: bool = False) -> None:
        super().__init__()
        self.return_tail = return_tail
        self.start_exclusive_values: list[int] = []

    def history_candles(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        start_exclusive_ms: int,
        **_kwargs,
    ):
        self.history_calls.append((instrument_id, timeframe))
        self.start_exclusive_values.append(start_exclusive_ms)
        if not self.return_tail:
            return _frame(timeframe).iloc[0:0].copy(), 1
        tail = _frame(timeframe).tail(1).copy()
        tail["timestamp_ms"] = tail["timestamp_ms"] + 15 * 60 * 1000
        tail["date"] = pd.to_datetime(tail["timestamp_ms"], unit="ms", utc=True)
        return tail, 1


class OfficialHistoryCollectorTests(unittest.TestCase):
    def test_different_contract_reuses_verified_shared_partition_and_checks_tail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layout = WarehouseLayout.from_root(Path(directory) / "回测数据")
            first_client = FakeOkxClient()
            first = OkxOfficialHistoryCollector(
                client=first_client,
                layout=layout,
            ).collect(_single_partition_contract("contract_a"))
            first_end_ms = int(
                pd.Timestamp(first.partitions[0].endTime).timestamp() * 1000
            )
            tail_client = TailRecordingOkxClient()

            second = OkxOfficialHistoryCollector(
                client=tail_client,
                layout=layout,
            ).collect(_single_partition_contract("contract_b"))

            self.assertEqual(second.status, "completed")
            self.assertEqual(second.reusedPartitionCount, 1)
            self.assertEqual(tail_client.start_exclusive_values, [first_end_ms])
            self.assertEqual(
                second.partitions[0].outputSha256,
                first.partitions[0].outputSha256,
            )

    def test_shared_partition_with_wrong_hash_is_not_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layout = WarehouseLayout.from_root(Path(directory) / "回测数据")
            OkxOfficialHistoryCollector(
                client=FakeOkxClient(),
                layout=layout,
            ).collect(_single_partition_contract("contract_a"))
            manifest = next((layout.officialRawRoot / "manifests").glob("*.json"))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["outputSha256"] = "invalid"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            client = TailRecordingOkxClient()

            OkxOfficialHistoryCollector(
                client=client,
                layout=layout,
            ).collect(_single_partition_contract("contract_b"))

            expected_start = int(
                pd.Timestamp("2020-01-01T00:00:00+00:00").timestamp() * 1000
            ) - 1
            self.assertEqual(client.start_exclusive_values, [expected_start])

    def test_malformed_shared_manifest_falls_back_to_official_collection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layout = WarehouseLayout.from_root(Path(directory) / "回测数据")
            OkxOfficialHistoryCollector(
                client=FakeOkxClient(),
                layout=layout,
            ).collect(_single_partition_contract("contract_a"))
            manifest = next((layout.officialRawRoot / "manifests").glob("*.json"))
            manifest.write_text("{malformed", encoding="utf-8")
            client = TailRecordingOkxClient(return_tail=True)

            result = OkxOfficialHistoryCollector(
                client=client,
                layout=layout,
            ).collect(_single_partition_contract("contract_b"))

            expected_start = int(
                pd.Timestamp("2020-01-01T00:00:00+00:00").timestamp() * 1000
            ) - 1
            self.assertEqual(result.status, "completed")
            self.assertEqual(client.start_exclusive_values, [expected_start])

    def test_shared_partition_merges_new_confirmed_tail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layout = WarehouseLayout.from_root(Path(directory) / "回测数据")
            first = OkxOfficialHistoryCollector(
                client=FakeOkxClient(),
                layout=layout,
            ).collect(_single_partition_contract("contract_a"))
            first_partition = first.partitions[0]
            tail_client = TailRecordingOkxClient(return_tail=True)

            second = OkxOfficialHistoryCollector(
                client=tail_client,
                layout=layout,
            ).collect(_single_partition_contract("contract_b"))

            second_partition = second.partitions[0]
            merged = pd.read_parquet(second_partition.outputPath)
            self.assertEqual(second.status, "completed")
            self.assertEqual(second_partition.status, "collected")
            self.assertEqual(second_partition.rows, first_partition.rows + 1)
            self.assertEqual(len(merged), first_partition.rows + 1)
            self.assertGreater(
                pd.Timestamp(second_partition.endTime),
                pd.Timestamp(first_partition.endTime),
            )

    def test_page_progress_is_durable_but_not_a_completed_partition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layout = WarehouseLayout.from_root(Path(directory) / "回测数据")
            checkpoint = (
                layout.checkpointRoot
                / "official-strategy_data_contract_official_test.json"
            )
            client = CheckpointInspectingOkxClient(checkpoint)

            result = OkxOfficialHistoryCollector(
                client=client,
                layout=layout,
            ).collect(_contract())

            self.assertEqual(result.status, "completed")
            first = client.progress_snapshots[0]
            self.assertEqual(first["instrumentId"], "BTC-USDT-SWAP")
            self.assertEqual(first["timeframe"], "15m")
            self.assertEqual(first["requestCount"], 1)
            self.assertEqual(first["rowCount"], 100)
            final_checkpoint = json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertNotIn("inProgress", final_checkpoint)
            self.assertEqual(len(final_checkpoint["completed"]), 4)

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
