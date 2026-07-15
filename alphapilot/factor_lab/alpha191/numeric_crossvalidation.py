"""Independent synthetic-fixture checks for preregistered Alpha191 formulas."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.factor_lab.expression_parser import parse_expression
from alphapilot.factor_lab.expression_runtime import evaluate_expression

from .external_crosscheck import classify_numeric_match
from .preregistration import build_seed_preregistration


def _safe_div(left: pd.Series, right: pd.Series | float) -> pd.Series:
    if isinstance(right, pd.Series):
        right = right.replace(0, np.nan)
    elif right == 0:
        right = np.nan
    return (left / right).replace([np.inf, -np.inf], np.nan)


def _fixture() -> dict[str, pd.Series]:
    index = pd.RangeIndex(72)
    close = pd.Series(100 + np.arange(72) * 0.15 + np.sin(np.arange(72) / 3), index=index)
    close.iloc[9] = 0.0
    close.iloc[33] = np.nan
    open_price = close.shift(1).fillna(100.0) + np.cos(np.arange(72) / 5) * 0.2
    high = pd.concat([open_price, close], axis=1).max(axis=1) + 0.8
    low = pd.concat([open_price, close], axis=1).min(axis=1) - 0.7
    volume = pd.Series(1000 + (np.arange(72) % 11) * 17.0, index=index)
    volume.iloc[20:25] = 1000.0
    volume.iloc[48] = 1_000_000.0
    return {"open": open_price, "high": high, "low": low, "close": close, "volume": volume}


def _manual_expected() -> dict[str, Callable[[dict[str, pd.Series]], pd.Series]]:
    return {
        "alpha191_014": lambda c: c["close"] - c["close"].shift(5),
        "alpha191_015": lambda c: _safe_div(c["open"], c["close"].shift(1)) - 1,
        "alpha191_018": lambda c: _safe_div(c["close"], c["close"].shift(5)),
        "alpha191_020": lambda c: _safe_div(
            c["close"] - c["close"].shift(6), c["close"].shift(6)
        )
        * 100,
        "alpha191_058": lambda c: (
            (c["close"] > c["close"].shift(1))
            .astype(float)
            .rolling(20, min_periods=20)
            .sum()
            / 20
            * 100
        ),
        "alpha191_088": lambda c: _safe_div(
            c["close"] - c["close"].shift(20), c["close"].shift(20)
        )
        * 100,
        "alpha191_145": lambda c: _safe_div(
            c["volume"].rolling(9, min_periods=9).mean()
            - c["volume"].rolling(26, min_periods=26).mean(),
            c["volume"].rolling(12, min_periods=12).mean(),
        )
        * 100,
        "alpha191_191": lambda c: (
            c["volume"]
            .rolling(20, min_periods=20)
            .mean()
            .rolling(5, min_periods=5)
            .corr(c["low"])
            + (c["high"] + c["low"]) / 2
            - c["close"]
        ),
    }


def run_numeric_crossvalidation() -> dict[str, object]:
    preregistration = build_seed_preregistration()
    fixture = _fixture()
    expected_functions = _manual_expected()
    results: list[dict[str, object]] = []
    for seed in preregistration["seedFactors"]:  # type: ignore[index]
        factor_id = str(seed["factorId"])
        actual = evaluate_expression(parse_expression(str(seed["canonicalFormula"])), fixture)
        expected = expected_functions[factor_id](fixture)
        actual_array = np.asarray(actual, dtype=float)
        expected_array = np.asarray(expected, dtype=float)
        status = classify_numeric_match(actual_array, expected_array, tolerance=1e-10)
        results.append(
            {
                "factorId": factor_id,
                "status": status,
                "maxAbsoluteError": float(
                    np.nanmax(np.abs(actual_array - expected_array))
                    if np.isfinite(actual_array - expected_array).any()
                    else 0.0
                ),
                "containsInfinity": bool(np.isinf(actual_array).any()),
                "fixtureRows": len(actual_array),
                "fixtureCases": [
                    "nan",
                    "zero_denominator",
                    "short_window",
                    "full_window",
                    "constant_segment",
                    "extreme_value",
                ],
            }
        )
    core = {
        "schemaVersion": "alpha191_numeric_crossvalidation_v1",
        "preregistrationHash": preregistration["preregistrationHash"],
        "seedCount": len(results),
        "formulaConflictCount": sum(item["status"] == "formula_conflict" for item in results),
        "unexpectedMismatchCount": sum(item["status"] == "unexpected_mismatch" for item in results),
        "results": results,
    }
    return {**core, "reportHash": stable_hash(core, prefix="numeric_crosscheck")}


def write_numeric_crossvalidation(output_path: Path) -> dict[str, object]:
    report = run_numeric_crossvalidation()
    report["preregistrationCommit"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
