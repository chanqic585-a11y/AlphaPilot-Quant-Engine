from __future__ import annotations

import unittest

from alphapilot.evolution.factor_dsl.canonicalizer import (
    canonical_expression,
    canonicalize,
    expression_id,
)
from alphapilot.evolution.factor_dsl.parser import parse_expression


class FactorCanonicalizerTests(unittest.TestCase):
    def test_commutative_operands_have_one_expression_id(self) -> None:
        left = canonicalize(parse_expression("close + volume"))
        right = canonicalize(parse_expression("volume + close"))

        self.assertEqual(expression_id(left), expression_id(right))
        self.assertEqual(canonical_expression(left), canonical_expression(right))

    def test_legacy_alias_and_number_format_are_normalized(self) -> None:
        legacy = canonicalize(parse_expression("ts_mean(close, 20.0)"))
        modern = canonicalize(parse_expression("rolling_mean(close, 20)"))

        self.assertEqual(expression_id(legacy), expression_id(modern))
        self.assertEqual(canonical_expression(legacy), "rolling_mean(close,20)")

    def test_ts_return_expands_to_point_in_time_safe_operators(self) -> None:
        expression = canonicalize(parse_expression("ts_return(close, 3)"))

        self.assertEqual(
            canonical_expression(expression),
            "safe_divide(delta(close,3),lag(close,3))",
        )

    def test_field_aliases_are_normalized(self) -> None:
        camel = canonicalize(parse_expression("btcReturn_12 + returns_1"))
        snake = canonicalize(parse_expression("btc_return_12 + returns_1"))

        self.assertEqual(expression_id(camel), expression_id(snake))


if __name__ == "__main__":
    unittest.main()
