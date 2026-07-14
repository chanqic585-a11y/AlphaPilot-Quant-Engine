from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.strategies.family_registry import ensure_strategy_family
from alphapilot.evolution.workflow.data_contract import (
    derive_strategy_data_contract,
    timeframe_plan,
)
from alphapilot.evolution.workflow.repository import WorkflowRepository
from alphapilot.evolution.workflow.service import register_strategy_version
from alphapilot.evolution.workflow.states import WorkflowConflict
from alphapilot.evolution.workflow.types import GateProfileRecord


class StrategyDataContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.connection = connect_registry(Path(self.temp.name) / "registry.sqlite")
        self.registry = RegistryRepository(self.connection)
        self.workflow = WorkflowRepository(self.connection)
        self.family = ensure_strategy_family(
            repository=self.registry,
            family_key="data-contract-test",
            name="Data Contract Test",
        )
        rules = {"minimumTargetR": 2.0}
        self.gate = self.workflow.create_gate_profile(
            GateProfileRecord(
                gateProfileId="gate_profile_data_contract_test_v1",
                profileKey="data_contract_test",
                version=1,
                stage="backtest",
                status="active",
                rules=rules,
                contentHash=stable_hash(rules),
            )
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def register_version(
        self,
        timeframe: str,
        *,
        target_r: float = 2.0,
        formal_data_plan: dict[str, str | None] | None = None,
    ):
        definition = {
            "direction": "both",
            "market": "crypto_usdt_swap",
            "timeframe": timeframe,
            "targetR": target_r,
        }
        if formal_data_plan is not None:
            definition["formalDataPlan"] = formal_data_plan
        return register_strategy_version(
            self.workflow,
            strategy_family_id=self.family.strategyFamilyId,
            display_name=f"Contract {timeframe} {target_r}",
            source_type="test",
            definition=definition,
            parameters={"timeframe": timeframe, "targetR": target_r},
            initial_gate_profile_id=self.gate.gateProfileId,
        )

    def test_timeframe_plan_supports_five_declared_strategy_classes(self) -> None:
        expected = {
            "5m": {"signal": "5m", "execution": "5m", "fallback": None},
            "15m": {"signal": "15m", "execution": "5m", "fallback": None},
            "1h": {"signal": "1h", "execution": "5m", "fallback": "15m"},
            "4h": {"signal": "4h", "execution": "5m", "fallback": "15m"},
            "1d": {"signal": "1d", "execution": "1h", "fallback": "4h"},
        }

        self.assertEqual(
            {timeframe: timeframe_plan(timeframe) for timeframe in expected},
            expected,
        )

    def test_contract_is_complete_and_idempotent_for_each_timeframe(self) -> None:
        for timeframe in ("5m", "15m", "1h", "4h", "1d"):
            with self.subTest(timeframe=timeframe):
                version = self.register_version(timeframe)
                first = derive_strategy_data_contract(version, self.workflow)
                second = derive_strategy_data_contract(version, self.workflow)

                self.assertEqual(first, second)
                self.assertEqual(first.strategyVersionId, version.strategyVersionId)
                self.assertEqual(first.contract["signalTimeframe"], timeframe)
                self.assertEqual(first.contract["targetR"], 2.0)
                self.assertEqual(first.contract["marketType"], "swap")
                self.assertEqual(
                    first.contract["requiredDataKinds"],
                    ["ohlcv", "funding", "instrument_metadata"],
                )
                self.assertTrue(
                    first.contract["validationPolicy"]["purgedWalkForward"]
                )
                self.assertTrue(
                    first.contract["validationPolicy"]["unseenSymbolHoldout"]
                )
                self.assertEqual(
                    first.contract["validationPolicy"]["sameBarAmbiguity"],
                    "stop_first",
                )
                self.assertEqual(
                    first.contract["universePolicy"]["ranking"],
                    "okx_public_24h_quote_notional_v1",
                )
                self.assertEqual(
                    first.contract["universePolicy"]["instrumentCategory"],
                    "1",
                )
                self.assertEqual(
                    first.contract["universePolicy"]["type"],
                    "current_snapshot_liquidity_ranked_crypto_usdt_swap",
                )
                self.assertFalse(
                    first.contract["universePolicy"]["historicalPointInTime"]
                )
                self.assertEqual(
                    first.contract["universePolicy"]["candidateDiscovery"],
                    ["okx_public_instruments", "okx_public_tickers"],
                )

    def test_invalid_timeframe_target_and_content_hash_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported_strategy_timeframe"):
            timeframe_plan("30m")

        low_target = self.register_version("4h", target_r=1.5)
        with self.assertRaisesRegex(ValueError, "target_r_below_2"):
            derive_strategy_data_contract(low_target, self.workflow)

        valid = self.register_version("1h")
        corrupted = replace(valid, contentHash="corrupted")
        with self.assertRaisesRegex(WorkflowConflict, "strategy_content_hash_mismatch"):
            derive_strategy_data_contract(corrupted, self.workflow)

    def test_allowlisted_four_hour_data_plan_reuses_fifteen_minute_store(self) -> None:
        version = self.register_version(
            "4h",
            formal_data_plan={
                "signal": "4h",
                "execution": "15m",
                "fallback": "1h",
            },
        )

        contract = derive_strategy_data_contract(version, self.workflow).contract

        self.assertEqual(contract["signalTimeframe"], "4h")
        self.assertEqual(contract["executionTimeframe"], "15m")
        self.assertEqual(contract["executionFallbackTimeframe"], "1h")

    def test_unapproved_or_mismatched_data_plan_fails_closed(self) -> None:
        invalid_plans = (
            {"signal": "4h", "execution": "1m", "fallback": "5m"},
            {"signal": "1h", "execution": "15m", "fallback": "1h"},
            {"signal": "1d", "execution": "4h", "fallback": None},
        )
        for plan in invalid_plans:
            with self.subTest(plan=plan):
                version = self.register_version(
                    str(plan["signal"]),
                    formal_data_plan=plan,
                )
                with self.assertRaisesRegex(ValueError, "unsupported_formal_data_plan"):
                    derive_strategy_data_contract(version, self.workflow)


if __name__ == "__main__":
    unittest.main()
