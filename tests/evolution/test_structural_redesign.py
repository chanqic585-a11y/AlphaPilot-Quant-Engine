from __future__ import annotations

import unittest

from alphapilot.evolution.workflow.structural_redesign import (
    MAX_STRUCTURAL_GENERATIONS,
    StructuralRedesignInput,
    build_structural_failure_profile,
    decide_structural_redesign,
)


GATE_RULES = {
    "minimumTargetR": 2.0,
    "minimumTradeCount": 30,
    "minimumProfitFactor": 1.1,
    "minimumAverageNetR": 0.0,
    "maximumDrawdownR": 20.0,
    "requiresCostStress": True,
}


def structural_metrics(
    *,
    trade_count: int = 200,
    profit_factor: float = 0.65,
    average_net_r: float = -0.24,
    maximum_drawdown_r: float = 42.0,
    stress_average_net_r: float = -0.12,
) -> dict:
    split = {
        "tradeCount": trade_count,
        "profitFactor": profit_factor,
        "averageNetR": average_net_r,
        "maximumDrawdownR": maximum_drawdown_r,
    }
    stress = {
        "tradeCount": trade_count,
        "averageNetR": stress_average_net_r,
    }
    return {
        "bySplit": {
            "development": dict(split),
            "walk_forward": dict(split),
            "holdout": {"profitFactor": 999.0, "averageNetR": 999.0},
            "locked_oos": {"profitFactor": 999.0, "averageNetR": 999.0},
        },
        "costStress": {
            "bySplit": {
                "development": dict(stress),
                "walk_forward": dict(stress),
                "holdout": {"averageNetR": 999.0},
                "locked_oos": {"averageNetR": 999.0},
            }
        },
    }


def structural_input(**overrides) -> StructuralRedesignInput:
    values = {
        "rootStrategyVersionId": "root-v1",
        "currentStrategyVersionId": "current-v1",
        "displayName": "15m EMA20 回收反弹 ATR1.4",
        "definition": {
            "schemaVersion": "short_cycle_strategy_definition_v1",
            "signalEngine": "short_cycle_v1",
            "signalFamily": "ema_reclaim_long",
            "market": "crypto_usdt_swap",
            "marketDataAccess": "public",
            "universePolicy": "point_in_time_dynamic_liquid_usdt_swap",
            "formalUniverseTarget": 50,
            "timeframe": "15m",
            "direction": "long",
            "targetR": 2.0,
            "exitPolicy": "two_r_half_atr_runner_v1",
            "researchOnly": True,
            "executionEnabled": False,
        },
        "parameters": {
            "trend_tolerance": 0.995,
            "reclaim_buffer": 0.003,
            "rsi_min": 42,
            "rsi_max": 72,
            "volume_min": 1.0,
            "stop_atr": 1.4,
            "max_hold": 16,
        },
        "metrics": structural_metrics(),
        "gateRules": GATE_RULES,
        "failureCategory": "strategy_performance",
        "runStatus": "failed",
        "usedRecipeIds": (),
        "activeStructuralChildExists": False,
    }
    values.update(overrides)
    return StructuralRedesignInput(**values)


class StructuralFailureProfileTests(unittest.TestCase):
    def test_profile_excludes_holdout_and_locked_evidence(self) -> None:
        profile = build_structural_failure_profile(structural_input())

        self.assertEqual(
            set(profile.metricsBySplit), {"development", "walk_forward"}
        )
        self.assertEqual(
            set(profile.costStressBySplit), {"development", "walk_forward"}
        )
        self.assertNotIn("holdout", repr(profile))
        self.assertNotIn("locked", repr(profile))
        self.assertTrue(profile.weakExpectancy)
        self.assertTrue(profile.drawdownConcentration)
        self.assertTrue(profile.transactionCostSensitive)

    def test_sparse_or_missing_selection_evidence_is_not_design_input(self) -> None:
        metrics = structural_metrics(trade_count=0)
        metrics["bySplit"]["walk_forward"] = {}

        decision = decide_structural_redesign(
            structural_input(metrics=metrics)
        )

        self.assertEqual(decision.action, "stop")
        self.assertEqual(decision.reasonCode, "selection_metrics_missing")
        self.assertIsNone(decision.proposedDefinition)


class StructuralRedesignDecisionTests(unittest.TestCase):
    def test_decision_is_deterministic_and_preserves_two_r(self) -> None:
        first = decide_structural_redesign(structural_input())
        second = decide_structural_redesign(structural_input())

        self.assertEqual(first, second)
        self.assertEqual(first.action, "create_child")
        self.assertEqual(first.generation, 1)
        self.assertEqual(first.maxGenerations, MAX_STRUCTURAL_GENERATIONS)
        self.assertEqual(first.recipeId, "regime_confirmed_trend_pullback_v1")
        self.assertEqual(first.proposedDefinition["targetR"], 2.0)
        self.assertEqual(first.proposedDefinition["direction"], "long")
        self.assertEqual(first.proposedDefinition["timeframe"], "15m")
        self.assertEqual(first.proposedDefinition["executionEnabled"], False)
        self.assertEqual(
            first.proposedDefinition["structuralRedesignLineage"]["generation"],
            1,
        )
        self.assertNotIn("holdout", repr(first))
        self.assertNotIn("locked", repr(first))

    def test_used_recipe_is_skipped_without_mutating_history(self) -> None:
        decision = decide_structural_redesign(
            structural_input(
                usedRecipeIds=("regime_confirmed_trend_pullback_v1",)
            )
        )

        self.assertEqual(decision.action, "create_child")
        self.assertEqual(
            decision.recipeId, "volatility_guarded_compression_release_v1"
        )
        self.assertEqual(decision.generation, 1)

    def test_all_used_recipes_stop_without_candidate(self) -> None:
        decision = decide_structural_redesign(
            structural_input(
                usedRecipeIds=(
                    "regime_confirmed_trend_pullback_v1",
                    "volatility_guarded_compression_release_v1",
                    "failed_reclaim_rejection_v1",
                )
            )
        )

        self.assertEqual(decision.action, "stop")
        self.assertEqual(decision.reasonCode, "no_novel_structural_recipe")
        self.assertIsNone(decision.proposedDefinition)

    def test_generation_three_failure_exhausts_structural_budget(self) -> None:
        definition = dict(structural_input().definition)
        definition["structuralRedesignLineage"] = {
            "schemaVersion": "structural_redesign_lineage_v1",
            "generation": 3,
            "maxGenerations": 3,
            "recipeId": "failed_reclaim_rejection_v1",
            "rootStrategyVersionId": "root-v1",
        }

        decision = decide_structural_redesign(
            structural_input(definition=definition)
        )

        self.assertEqual(decision.action, "stop")
        self.assertEqual(
            decision.reasonCode, "structural_generation_budget_exhausted"
        )
        self.assertEqual(decision.generation, 3)

    def test_active_structural_child_waits(self) -> None:
        decision = decide_structural_redesign(
            structural_input(activeStructuralChildExists=True)
        )

        self.assertEqual(decision.action, "wait")
        self.assertEqual(decision.reasonCode, "active_structural_child_exists")
        self.assertIsNone(decision.proposedDefinition)

    def test_non_performance_failure_never_redesigns(self) -> None:
        decision = decide_structural_redesign(
            structural_input(
                failureCategory="worker_operational",
                metrics={},
                runStatus="blocked",
            )
        )

        self.assertEqual(decision.action, "stop")
        self.assertEqual(decision.reasonCode, "non_performance_failure")
        self.assertIsNone(decision.proposedDefinition)

    def test_target_below_two_r_never_redesigns(self) -> None:
        definition = dict(structural_input().definition)
        definition["targetR"] = 1.9

        decision = decide_structural_redesign(
            structural_input(definition=definition)
        )

        self.assertEqual(decision.action, "stop")
        self.assertEqual(decision.reasonCode, "minimum_target_r_violation")
        self.assertIsNone(decision.proposedDefinition)


if __name__ == "__main__":
    unittest.main()
