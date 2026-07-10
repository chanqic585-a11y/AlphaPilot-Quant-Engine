from __future__ import annotations

import unittest

from alphapilot.evolution.factor_dsl.ast import BinaryOp, FunctionCall, ast_to_dict
from alphapilot.evolution.factor_dsl.parser import FactorSyntaxError, parse_expression


class FactorDslParserTests(unittest.TestCase):
    def test_parses_nested_whitelisted_expression(self) -> None:
        expression = parse_expression(
            "rolling_mean(close, 20) + safe_divide(volume, lag(volume, 1))"
        )

        self.assertIsInstance(expression, BinaryOp)
        self.assertEqual(expression.operator, "+")
        self.assertIsInstance(expression.left, FunctionCall)
        self.assertEqual(expression.left.name, "rolling_mean")
        self.assertEqual(ast_to_dict(expression)["type"], "binary")

    def test_parses_comparison_for_where_condition(self) -> None:
        expression = parse_expression("where(close > lag(close, 1), close, lag(close, 1))")

        self.assertIsInstance(expression, FunctionCall)
        self.assertEqual(expression.name, "where")
        self.assertEqual(ast_to_dict(expression)["args"][0]["type"], "comparison")

    def test_rejects_unsafe_or_malformed_syntax(self) -> None:
        invalid = [
            "close.__class__",
            "__import__(close)",
            "unknown_function(close)",
            "open(close)",
            "'close'",
            "import os",
            "rolling_mean(close, 20",
            "close[0]",
            "close; volume",
        ]

        for expression in invalid:
            with self.subTest(expression=expression):
                with self.assertRaises(FactorSyntaxError):
                    parse_expression(expression)


if __name__ == "__main__":
    unittest.main()
