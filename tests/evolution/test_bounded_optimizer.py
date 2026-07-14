from __future__ import annotations

import unittest

from alphapilot.evolution.workflow.bounded_optimizer import (
    MAX_AUTOMATIC_ATTEMPTS,
    OptimizationInput,
    decide_bounded_optimization,
    evaluate_selection_gate,
    sanitize_selection_metrics,
)


GATE_RULES = {
    "minimumTargetR": 2.0,
    "minimumTradeCount": 30,
    "minimumProfitFactor": 1.1,
    "minimumAverageNetR": 0.0,
    "maximumDrawdownR": 20.0,
    "requiresCostStress": True,
}


def selection_metrics(
    *,
    profit_factor: float = 1.05,
    average_net_r: float = 0.04,
    trade_count: int = 30,
    drawdown_r: float = 8.0,
    stress_average_net_r: float = 0.01,
) -> dict:
    split = {
        "tradeCount": trade_count,
        "profitFactor": profit_factor,
        "averageNetR": average_net_r,
        "maximumDrawdownR": drawdown_r,
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


def input_for(**overrides) -> OptimizationInput:
    values = {
        "rootStrategyVersionId": "root-v1",
        "currentStrategyVersionId": "current-v1",
        "displayName": "15m EMA20 回收反弹 ATR1.4",
        "definition": {
            "signalFamily": "ema_reclaim_long",
            "timeframe": "15m",
            "direction": "long",
            "targetR": 2.0,
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
        "metrics": selection_metrics(),
        "gateRules": GATE_RULES,
        "failureCategory": "strategy_performance",
        "runStatus": "failed",
        "completedAttempts": 0,
        "activeChallengerExists": False,
    }
    values.update(overrides)
    return OptimizationInput(**values)


class BoundedOptimizerTests(unittest.TestCase):
    def test_selection_metrics_exclude_holdout_and_locked(self) -> None:
        sanitized = sanitize_selection_metrics(selection_metrics())

        self.assertEqual(
            set(sanitized["bySplit"]), {"development", "walk_forward"}
        )
        self.assertEqual(
            set(sanitized["costStress"]["bySplit"]),
            {"development", "walk_forward"},
        )
        self.assertNotIn("holdout", repr(sanitized))
        self.assertNotIn("locked", repr(sanitized))

    def test_selection_gate_uses_only_selection_splits(self) -> None:
        metrics = selection_metrics(profit_factor=1.2, average_net_r=0.1)
        metrics["bySplit"]["holdout"] = {"tradeCount": 0, "profitFactor": 0}
        metrics["bySplit"]["locked_oos"] = {"tradeCount": 0, "profitFactor": 0}

        checks = evaluate_selection_gate(
            sanitize_selection_metrics(metrics),
            gate_rules=GATE_RULES,
            target_r=2.0,
        )

        self.assertTrue(all(checks.values()))

    def test_data_or_worker_failure_never_creates_challenger(self) -> None:
        decision = decide_bounded_optimization(
            input_for(failureCategory="worker_operational", metrics={})
        )

        self.assertEqual(decision.action, "stop")
        self.assertEqual(decision.terminalStatus, "data_evidence_blocked")
        self.assertIsNone(decision.proposedParameters)

    def test_structurally_weak_development_stops_early(self) -> None:
        decision = decide_bounded_optimization(
            input_for(
                metrics=selection_metrics(
                    profit_factor=0.7,
                    average_net_r=-0.2,
                    drawdown_r=40,
                    stress_average_net_r=-0.1,
                )
            )
        )

        self.assertEqual(decision.action, "stop")
        self.assertEqual(
            decision.terminalStatus, "structural_redesign_required"
        )

    def test_mutation_is_deterministic_allowlisted_and_keeps_two_r(self) -> None:
        first = decide_bounded_optimization(input_for())
        second = decide_bounded_optimization(input_for())

        self.assertEqual(first, second)
        self.assertEqual(first.action, "create_challenger")
        self.assertEqual(first.attemptNumber, 1)
        self.assertEqual(first.changedParameter["name"], "volume_min")
        self.assertEqual(first.proposedParameters["volume_min"], 1.2)
        self.assertEqual(first.proposedDefinition["targetR"], 2.0)
        self.assertEqual(
            first.proposedDefinition["exitPolicy"],
            "two_r_half_atr_runner_v1",
        )
        self.assertEqual(
            first.proposedDefinition["optimizationLineage"]["phase"],
            "selection",
        )

    def test_only_one_active_challenger_is_allowed(self) -> None:
        decision = decide_bounded_optimization(
            input_for(activeChallengerExists=True)
        )

        self.assertEqual(decision.action, "wait")
        self.assertEqual(decision.reasonCode, "active_challenger_exists")
        self.assertIsNone(decision.terminalStatus)

    def test_budget_exhaustion_stops_after_three_attempts(self) -> None:
        decision = decide_bounded_optimization(
            input_for(completedAttempts=MAX_AUTOMATIC_ATTEMPTS)
        )

        self.assertEqual(decision.action, "stop")
        self.assertEqual(decision.terminalStatus, "budget_exhausted")

    def test_unsupported_family_stops_without_guessing(self) -> None:
        decision = decide_bounded_optimization(
            input_for(definition={"signalFamily": "unknown", "targetR": 2.0})
        )

        self.assertEqual(decision.action, "stop")
        self.assertEqual(
            decision.terminalStatus, "structural_redesign_required"
        )
        self.assertEqual(decision.reasonCode, "parameter_allowlist_missing")

    def test_all_windowed_families_have_bounded_parameter_mutations(self) -> None:
        fixtures = {
            "windowed_breakout_retest_long": {
                "breakout_volume_min": 1.0,
                "confirmation_volume_min": 0.9,
                "reclaim_buffer": 0.001,
            },
            "windowed_failed_breakout_short": {
                "volume_min": 1.0,
                "rsi_high": 62,
                "rejection_buffer": 0.0003,
            },
            "windowed_failed_reclaim_short": {
                "volume_min": 1.0,
                "rsi_max": 62,
                "rejection_buffer": 0.0003,
            },
            "windowed_liquidity_sweep_reclaim_long": {
                "volume_min": 1.0,
                "rsi_oversold": 30,
                "reclaim_buffer": 0.0003,
            },
            "windowed_recovery_reclaim_long": {
                "volume_min": 1.0,
                "rsi_min": 42,
                "trend_floor": 0.98,
            },
            "windowed_squeeze_breakout_long": {
                "volume_min": 1.0,
                "squeeze_ratio": 0.8,
                "breakout_buffer": 0.0003,
            },
            "windowed_trend_reclaim_long": {
                "volume_min": 1.0,
                "rsi_min": 42,
                "reclaim_buffer": 0.0003,
            },
        }

        for family, parameters in fixtures.items():
            with self.subTest(family=family):
                decision = decide_bounded_optimization(
                    input_for(
                        definition={"signalFamily": family, "targetR": 2.0},
                        parameters=parameters,
                    )
                )

                self.assertEqual(decision.action, "create_challenger")
                self.assertEqual(decision.terminalStatus, None)
                self.assertEqual(decision.attemptNumber, 1)
                self.assertEqual(decision.proposedDefinition["targetR"], 2.0)
                self.assertNotEqual(decision.proposedParameters, parameters)

    def test_passed_selection_creates_one_formal_validation_version(self) -> None:
        definition = dict(input_for().definition)
        definition["optimizationLineage"] = {
            "phase": "selection",
            "rootStrategyVersionId": "root-v1",
            "attemptNumber": 2,
            "maxAttempts": 3,
        }
        decision = decide_bounded_optimization(
            input_for(
                definition=definition,
                metrics=selection_metrics(profit_factor=1.3, average_net_r=0.1),
                runStatus="passed",
                completedAttempts=2,
            )
        )

        self.assertEqual(decision.action, "create_formal_validation")
        self.assertTrue(
            decision.proposedDefinition["optimizationLineage"][
                "formalValidationConsumed"
            ]
        )

    def test_failed_formal_validation_is_terminal(self) -> None:
        definition = dict(input_for().definition)
        definition["optimizationLineage"] = {
            "phase": "formal_validation",
            "rootStrategyVersionId": "root-v1",
            "attemptNumber": 2,
            "maxAttempts": 3,
            "formalValidationConsumed": True,
        }
        decision = decide_bounded_optimization(input_for(definition=definition))

        self.assertEqual(decision.action, "stop")
        self.assertEqual(decision.terminalStatus, "formal_validation_failed")

    def test_target_below_two_r_is_never_mutated_or_accepted(self) -> None:
        decision = decide_bounded_optimization(
            input_for(definition={**input_for().definition, "targetR": 1.9})
        )

        self.assertEqual(decision.action, "stop")
        self.assertEqual(decision.reasonCode, "minimum_target_r_violation")


if __name__ == "__main__":
    unittest.main()
