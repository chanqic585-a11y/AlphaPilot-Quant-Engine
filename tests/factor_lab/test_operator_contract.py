from __future__ import annotations

from alphapilot.factor_lab.operator_contract import REQUIRED_OPERATOR_NAMES, validate_operator_contract


def test_all_required_operators_are_registered() -> None:
    errors = validate_operator_contract()

    assert errors == []
    assert "safe_div" in REQUIRED_OPERATOR_NAMES
    assert "rolling_residual" in REQUIRED_OPERATOR_NAMES
