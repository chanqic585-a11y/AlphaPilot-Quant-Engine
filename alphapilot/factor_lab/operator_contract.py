"""Contract checks for the public factor operator surface."""

from __future__ import annotations

import inspect

from .operators import OPERATOR_REGISTRY


REQUIRED_OPERATOR_NAMES = (
    "rank",
    "zscore",
    "scale",
    "winsorize",
    "delay",
    "delta",
    "ts_rank",
    "ts_corr",
    "ts_cov",
    "ts_mean",
    "ts_std",
    "ts_sum",
    "ts_product",
    "ts_min",
    "ts_max",
    "ts_argmin",
    "ts_argmax",
    "ts_ema",
    "ts_slope",
    "decay_linear",
    "safe_div",
    "signed_power",
    "count",
    "sum_if",
    "rolling_beta",
    "rolling_residual",
    "conditional_select",
)


def validate_operator_contract() -> list[str]:
    errors: list[str] = []
    for name in REQUIRED_OPERATOR_NAMES:
        operator = OPERATOR_REGISTRY.get(name)
        if operator is None:
            errors.append(f"missing operator: {name}")
            continue
        parameters = inspect.signature(operator).parameters
        if name.startswith("ts_") or name in {
            "decay_linear",
            "count",
            "sum_if",
            "rolling_beta",
            "rolling_residual",
        }:
            min_periods = parameters.get("min_periods")
            if min_periods is None or min_periods.default is not inspect.Parameter.empty:
                errors.append(f"{name}: min_periods must be explicit")
    return errors
