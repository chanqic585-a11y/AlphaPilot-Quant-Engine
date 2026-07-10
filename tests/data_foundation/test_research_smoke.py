from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from alphapilot.data_foundation.research_smoke import run_research_smoke
from alphapilot.data_foundation.warehouse import WarehouseLayout
from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.evolution.workflow.types import StrategyDataContractRecord


def _contract() -> StrategyDataContractRecord:
    payload = {
        "schemaVersion": "strategy_data_contract_v1",
        "strategyVersionId": "strategy_version_test",
        "strategyContentHash": "strategy_hash_test",
        "marketType": "swap",
        "direction": "both",
        "signalTimeframe": "5m",
        "executionTimeframe": "5m",
        "executionFallbackTimeframe": None,
        "targetR": 2.0,
    }
    return StrategyDataContractRecord(
        strategyDataContractId="strategy_data_contract_test",
        strategyVersionId="strategy_version_test",
        schemaVersion="strategy_data_contract_v1",
        contract=payload,
        contentHash="strategy_data_contract_test",
    )


class ResearchSmokeTests(unittest.TestCase):
    def test_local_csv_smoke_is_implementation_valid_but_never_formal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layout = WarehouseLayout.from_root(Path(directory) / "回测数据")
            layout.ensure_directories()
            source = layout.localFiveMinuteRoot / "BTC_USDT_5m_from_20260101.csv"
            source.parent.mkdir(parents=True, exist_ok=True)
            timestamps = pd.date_range(
                "2026-01-01", periods=240, freq="5min", tz="UTC"
            )
            frame = pd.DataFrame(
                {
                    "timestamp": timestamps.astype("int64") // 1_000_000,
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "vol": 10.0,
                    "confirm": 1,
                }
            )
            frame.to_csv(source, index=False)
            source_hash = sha256_file(source)
            output = layout.reportRoot / "research-smoke.json"

            result = run_research_smoke(_contract(), layout, output)

            self.assertEqual(result["status"], "completed")
            self.assertTrue(result["implementationValid"])
            self.assertEqual(result["evidenceClass"], "research_smoke")
            self.assertFalse(result["formalPromotionEligible"])
            self.assertEqual(result["selectedAssetCount"], 1)
            self.assertEqual(result["assets"][0]["symbol"], "BTC")
            self.assertNotIn("passedFormalGate", result)
            self.assertEqual(sha256_file(source), source_hash)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)

    def test_missing_local_assets_blocks_smoke_without_claiming_formal_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            layout = WarehouseLayout.from_root(Path(directory) / "回测数据")
            layout.ensure_directories()

            result = run_research_smoke(
                _contract(), layout, layout.reportRoot / "empty-smoke.json"
            )

            self.assertEqual(result["status"], "blocked")
            self.assertFalse(result["implementationValid"])
            self.assertEqual(result["blockers"], ["local_research_assets_missing"])
            self.assertEqual(result["evidenceClass"], "research_smoke")
            self.assertFalse(result["formalPromotionEligible"])


if __name__ == "__main__":
    unittest.main()
