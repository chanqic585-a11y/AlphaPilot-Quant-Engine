from __future__ import annotations

import pandas as pd
import pytest

from alphapilot.factor_lab.expression_parser import parse_expression
from alphapilot.factor_lab.expression_runtime import evaluate_expression


def test_whitelisted_expression_executes_without_eval() -> None:
    close = pd.Series([10.0, 11.0, 13.0, 12.0])
    expression = parse_expression("safe_div(delta(close, 1), delay(close, 1))")

    result = evaluate_expression(expression, {"close": close})

    assert result.iloc[2] == pytest.approx(2.0 / 11.0)


@pytest.mark.parametrize(
    "source",
    [
        "eval('1+1')",
        "__import__('os')",
        "close.__class__",
        "close[0]",
        "open('secret')",
        "rank(rank(close))",
        "ts_mean(ts_mean(close, 2, 2), 2, 2)",
    ],
)
def test_parser_rejects_unsafe_or_unexplained_expressions(source: str) -> None:
    with pytest.raises(ValueError):
        parse_expression(source)


def test_parser_enforces_depth_and_operator_budget() -> None:
    with pytest.raises(ValueError, match="depth|operator"):
        parse_expression("abs(abs(abs(abs(abs(close)))))")
