from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from alphapilot.evolution.factor_dsl import parse_expression, validate_factor_expression
from alphapilot.evolution.factor_runs.definitions import DEFAULT_FACTOR_SPECS, FACTOR_FIELD_TYPES
from alphapilot.evolution.factor_runs.evaluator import evaluate_factor_expression


class FactorRunEvaluatorTests(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        close = np.linspace(100.0, 130.0, 120)
        return pd.DataFrame(
            {
                "open": close - 0.2,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": np.linspace(1_000.0, 2_000.0, 120),
            }
        )

    def test_default_factor_specs_validate_and_materialize(self) -> None:
        frame = self._frame()
        for spec in DEFAULT_FACTOR_SPECS:
            expression = parse_expression(spec.expression)
            validation = validate_factor_expression(expression, field_types=FACTOR_FIELD_TYPES)
            self.assertTrue(validation.valid, (spec.factorId, validation.issues))
            result = evaluate_factor_expression(expression, frame)
            self.assertEqual(len(result), len(frame))
            self.assertGreater(result.notna().sum(), 0, spec.factorId)

    def test_future_rows_do_not_change_an_earlier_factor_value(self) -> None:
        frame = self._frame()
        decision_index = 80
        for spec in DEFAULT_FACTOR_SPECS:
            expression = parse_expression(spec.expression)
            baseline = evaluate_factor_expression(expression, frame).iloc[decision_index]
            mutated = frame.copy()
            mutated.loc[decision_index + 1 :, ["open", "high", "low", "close", "volume"]] *= 100
            changed = evaluate_factor_expression(expression, mutated).iloc[decision_index]
            if pd.isna(baseline):
                self.assertTrue(pd.isna(changed), spec.factorId)
            else:
                self.assertAlmostEqual(float(baseline), float(changed), places=12, msg=spec.factorId)


if __name__ == "__main__":
    unittest.main()
