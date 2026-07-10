from __future__ import annotations

import unittest

from alphapilot.evolution.factor_dsl.parser import parse_expression
from alphapilot.evolution.factor_dsl.validator import validate_factor_expression


FIELD_TYPES = {
    "close": "number",
    "volume": "number",
    "returns_1": "number",
    "regime_label": "group",
}


class FactorDslValidatorTests(unittest.TestCase):
    def test_valid_expression_reports_fields_and_domain_requirements(self) -> None:
        result = validate_factor_expression(
            parse_expression("safe_log(safe_divide(delta(close, 1), lag(close, 1)))"),
            field_types=FIELD_TYPES,
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.requiredFields, ["close"])
        self.assertIn("denominator_nonzero", result.domainRequirements)
        self.assertIn("log_input_positive", result.domainRequirements)

    def test_rejects_unknown_fields_bad_windows_and_future_offsets(self) -> None:
        cases = {
            "rolling_mean(missing, 20)": "unknown_field",
            "rolling_mean(close, 0)": "window_out_of_range",
            "rolling_mean(close, 9999)": "window_out_of_range",
            "lag(close, -1)": "future_offset_forbidden",
            "safe_divide(close, 0)": "division_by_zero_literal",
        }

        for expression, expected_code in cases.items():
            with self.subTest(expression=expression):
                result = validate_factor_expression(
                    parse_expression(expression),
                    field_types=FIELD_TYPES,
                    max_window=512,
                )
                self.assertFalse(result.valid)
                self.assertIn(expected_code, [issue.code for issue in result.issues])

    def test_rejects_excessive_nesting_and_type_mismatch(self) -> None:
        nested = "close"
        for _ in range(8):
            nested = f"safe_log({nested})"
        depth_result = validate_factor_expression(
            parse_expression(nested),
            field_types=FIELD_TYPES,
            max_depth=6,
        )
        type_result = validate_factor_expression(
            parse_expression("safe_add(close, regime_label)"),
            field_types=FIELD_TYPES,
        )

        self.assertIn("max_depth_exceeded", [issue.code for issue in depth_result.issues])
        self.assertIn("type_mismatch", [issue.code for issue in type_result.issues])

    def test_safe_sqrt_and_group_neutralize_metadata(self) -> None:
        result = validate_factor_expression(
            parse_expression("group_neutralize(safe_sqrt(close), regime_label)"),
            field_types=FIELD_TYPES,
        )

        self.assertTrue(result.valid)
        self.assertIn("sqrt_input_nonnegative", result.domainRequirements)


if __name__ == "__main__":
    unittest.main()
