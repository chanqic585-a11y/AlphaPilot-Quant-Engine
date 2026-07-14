import tempfile
import unittest
from pathlib import Path

import pandas as pd

from alphapilot.data_foundation.local_formal_history import (
    LocalFormalHistoryCollector,
)
from alphapilot.data_foundation.checkpoint import load_json
from alphapilot.data_foundation.warehouse import WarehouseLayout
from alphapilot.evolution.workflow.types import StrategyDataContractRecord


def make_contract(*, minimum_members: int = 2) -> StrategyDataContractRecord:
    contract = {
        "marketType": "swap",
        "signalTimeframe": "4h",
        "executionTimeframe": "15m",
        "executionFallbackTimeframe": None,
        "requestedStart": "2020-01-01T00:00:00+00:00",
        "universePolicy": {
            "minimumMembers": minimum_members,
            "targetMembers": minimum_members,
        },
        "costPolicy": {"fundingRequiredForSwap": True},
    }
    return StrategyDataContractRecord(
        strategyDataContractId="strategy_data_contract_local_test",
        strategyVersionId="strategy_version_local_test",
        schemaVersion="strategy_data_contract_v1",
        contract=contract,
        contentHash="strategy_data_contract_local_test",
    )


def write_swap_ohlcv(root: Path, symbol: str, timeframe: str) -> None:
    dates = pd.date_range(
        "2020-01-01",
        periods=360,
        freq={"15m": "15min", "4h": "4h"}[timeframe],
        tz="UTC",
    )
    close = pd.Series(range(len(dates)), dtype="float64") * 0.01 + 100.0
    frame = pd.DataFrame(
        {
            "market_type": "swap",
            "inst_id": f"{symbol}-USDT-SWAP",
            "bar": timeframe,
            "timestamp_ms": dates.as_unit("ms").astype("int64"),
            "date": dates.tz_localize(None),
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close + 0.25,
            "volume_quote_currency": 1000.0,
            "confirmed": 1,
        }
    )
    path = (
        root
        / "合约数据"
        / f"swap_candles_{timeframe}"
        / f"{symbol}_USDT_SWAP"
        / f"{symbol}_USDT_SWAP_swap_candles_{timeframe}_ALL.xlsx"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_excel(path, index=False)


def write_funding(root: Path, symbol: str) -> None:
    path = (
        root
        / "合约数据"
        / "funding_rates"
        / f"{symbol}_USDT_SWAP"
        / f"{symbol}_USDT_SWAP_funding_rates_ALL.xlsx"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "inst_id": [f"{symbol}-USDT-SWAP"],
            "funding_time_ms": [1577836800000],
            "funding_rate": [0.0001],
        }
    ).to_excel(path, index=False)


class LocalFormalHistoryCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "回测数据"
        self.layout = WarehouseLayout.from_root(self.root)
        self.layout.ensure_directories()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_builds_complete_formal_collection_from_local_files_only(self) -> None:
        for symbol in ("BTC", "ETH"):
            write_swap_ohlcv(self.root, symbol, "15m")
            write_swap_ohlcv(self.root, symbol, "4h")
            write_funding(self.root, symbol)

        first = LocalFormalHistoryCollector(layout=self.layout).collect(
            make_contract()
        )
        second = LocalFormalHistoryCollector(layout=self.layout).collect(
            make_contract()
        )

        self.assertEqual(first.status, "completed")
        self.assertEqual(first.instrumentCount, 2)
        self.assertEqual(first.completedPartitionCount, 4)
        self.assertEqual(first.failedPartitionCount, 0)
        self.assertEqual(first.fundingFileCount, 2)
        self.assertTrue(
            all(item.provenanceStatus == "user_approved_local" for item in first.partitions)
        )
        self.assertTrue(all(item.requestCount == 0 for item in first.partitions))
        self.assertEqual(second.reusedPartitionCount, 4)

    def test_missing_local_coverage_blocks_without_downloading(self) -> None:
        write_swap_ohlcv(self.root, "BTC", "15m")
        write_swap_ohlcv(self.root, "BTC", "4h")
        write_funding(self.root, "BTC")

        result = LocalFormalHistoryCollector(layout=self.layout).collect(
            make_contract(minimum_members=2)
        )

        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.instrumentCount, 1)
        self.assertEqual(result.failedPartitionCount, 1)
        self.assertEqual(result.completedPartitionCount, 0)
        self.assertEqual(result.fundingFileCount, 0)
        self.assertEqual(list(self.layout.officialRawRoot.iterdir()), [])

    def test_pause_keeps_incremental_local_conversion_progress(self) -> None:
        for symbol in ("BTC", "ETH"):
            write_swap_ohlcv(self.root, symbol, "15m")
            write_swap_ohlcv(self.root, symbol, "4h")
            write_funding(self.root, symbol)
        checks = 0

        def stop_after_first() -> bool:
            nonlocal checks
            checks += 1
            return checks > 1

        result = LocalFormalHistoryCollector(
            layout=self.layout,
            stop_requested=stop_after_first,
        ).collect(make_contract())
        checkpoint = load_json(Path(result.checkpointPath))

        self.assertEqual(result.status, "paused")
        self.assertEqual(result.instrumentCount, 1)
        self.assertEqual(checkpoint["status"], "paused")
        self.assertEqual(checkpoint["selectedInstruments"], ["BTC-USDT-SWAP"])


if __name__ == "__main__":
    unittest.main()
