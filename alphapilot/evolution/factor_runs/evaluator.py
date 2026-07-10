"""Pandas evaluator for validated, point-in-time factor DSL expressions."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from alphapilot.evolution.factor_dsl.ast import (
    BinaryOp,
    ComparisonOp,
    Expression,
    FieldReference,
    FunctionCall,
    NumberLiteral,
    UnaryOp,
)


def _series(value: Any, index: pd.Index) -> pd.Series:
    if isinstance(value, pd.Series):
        return value.astype("float64")
    return pd.Series(float(value), index=index, dtype="float64")


def _integer(value: Any, name: str) -> int:
    if isinstance(value, pd.Series):
        raise ValueError(f"{name} must be a scalar integer")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed != int(parsed) or parsed <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return int(parsed)


def _rolling_rank(values: np.ndarray) -> float:
    if np.isnan(values).any():
        return float("nan")
    return float(pd.Series(values).rank(pct=True).iloc[-1])


def _decay(values: np.ndarray) -> float:
    if np.isnan(values).any():
        return float("nan")
    weights = np.arange(1, len(values) + 1, dtype="float64")
    return float(np.dot(values, weights) / weights.sum())


def evaluate_factor_expression(node: Expression, frame: pd.DataFrame) -> pd.Series:
    """Evaluate one already validated expression using current and prior rows only."""

    index = frame.index

    def visit(current: Expression) -> Any:
        if isinstance(current, NumberLiteral):
            return float(current.value)
        if isinstance(current, FieldReference):
            if current.name not in frame.columns:
                raise ValueError(f"Missing factor field: {current.name}")
            return pd.to_numeric(frame[current.name], errors="coerce").astype("float64")
        if isinstance(current, UnaryOp):
            operand = visit(current.operand)
            return operand if current.operator == "+" else -operand
        if isinstance(current, BinaryOp):
            left = visit(current.left)
            right = visit(current.right)
            if current.operator == "+":
                return left + right
            if current.operator == "-":
                return left - right
            if current.operator == "*":
                return left * right
            if current.operator == "/":
                denominator = _series(right, index).replace(0, np.nan)
                return _series(left, index) / denominator
            raise ValueError(f"Unsupported binary operator: {current.operator}")
        if isinstance(current, ComparisonOp):
            left = visit(current.left)
            right = visit(current.right)
            operators = {
                "<": lambda: left < right,
                "<=": lambda: left <= right,
                ">": lambda: left > right,
                ">=": lambda: left >= right,
                "==": lambda: left == right,
                "!=": lambda: left != right,
            }
            if current.operator not in operators:
                raise ValueError(f"Unsupported comparison operator: {current.operator}")
            return operators[current.operator]()
        if not isinstance(current, FunctionCall):
            raise TypeError(f"Unsupported factor node: {type(current).__name__}")

        args = [visit(arg) for arg in current.args]
        name = current.name
        if name == "lag":
            return _series(args[0], index).shift(_integer(args[1], "lag"))
        if name == "delta":
            values = _series(args[0], index)
            return values - values.shift(_integer(args[1], "delta"))
        if name in {"rolling_mean", "rolling_std", "rolling_min", "rolling_max"}:
            values = _series(args[0], index)
            window = _integer(args[1], name)
            rolling = values.rolling(window, min_periods=window)
            if name == "rolling_mean":
                return rolling.mean()
            if name == "rolling_std":
                return rolling.std(ddof=0)
            if name == "rolling_min":
                return rolling.min()
            return rolling.max()
        if name == "rolling_rank":
            window = _integer(args[1], name)
            return _series(args[0], index).rolling(window, min_periods=window).apply(
                _rolling_rank, raw=True
            )
        if name == "zscore":
            values = _series(args[0], index)
            window = _integer(args[1], name)
            rolling = values.rolling(window, min_periods=window)
            return (values - rolling.mean()) / rolling.std(ddof=0).replace(0, np.nan)
        if name == "correlation":
            window = _integer(args[2], name)
            return _series(args[0], index).rolling(window, min_periods=window).corr(
                _series(args[1], index)
            )
        if name == "decay_linear":
            window = _integer(args[1], name)
            return _series(args[0], index).rolling(window, min_periods=window).apply(
                _decay, raw=True
            )
        if name == "ewm_mean":
            span = _integer(args[1], name)
            return _series(args[0], index).ewm(span=span, adjust=False, min_periods=span).mean()
        if name == "rsi":
            window = _integer(args[1], name)
            delta = _series(args[0], index).diff()
            gains = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
            losses = (-delta.clip(upper=0)).ewm(
                alpha=1 / window, adjust=False, min_periods=window
            ).mean()
            relative_strength = gains / losses.replace(0, np.nan)
            result = 100 - (100 / (1 + relative_strength))
            return result.mask((losses == 0) & (gains > 0), 100.0).mask(
                (losses == 0) & (gains == 0), 50.0
            )
        if name == "macd_histogram":
            values = _series(args[0], index)
            fast = _integer(args[1], "macd fast")
            slow = _integer(args[2], "macd slow")
            signal = _integer(args[3], "macd signal")
            if fast >= slow:
                raise ValueError("MACD fast window must be less than slow window")
            line = values.ewm(span=fast, adjust=False, min_periods=slow).mean() - values.ewm(
                span=slow, adjust=False, min_periods=slow
            ).mean()
            signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
            return line - signal_line
        if name == "bollinger_position":
            values = _series(args[0], index)
            window = _integer(args[1], name)
            width = float(args[2])
            if not math.isfinite(width) or width <= 0:
                raise ValueError("Bollinger width must be positive")
            rolling = values.rolling(window, min_periods=window)
            return (values - rolling.mean()) / (rolling.std(ddof=0) * width).replace(0, np.nan)
        if name == "atr":
            high = _series(args[0], index)
            low = _series(args[1], index)
            close = _series(args[2], index)
            window = _integer(args[3], name)
            previous_close = close.shift(1)
            true_range = pd.concat(
                [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
                axis=1,
            ).max(axis=1)
            return true_range.rolling(window, min_periods=window).mean()
        if name in {"safe_add", "safe_subtract", "safe_multiply", "safe_divide"}:
            left = _series(args[0], index)
            right = _series(args[1], index)
            if name == "safe_add":
                return left + right
            if name == "safe_subtract":
                return left - right
            if name == "safe_multiply":
                return left * right
            return left / right.replace(0, np.nan)
        if name == "safe_log":
            values = _series(args[0], index)
            return np.log(values.where(values > 0))
        if name == "safe_sqrt":
            values = _series(args[0], index)
            return np.sqrt(values.where(values >= 0))
        if name == "where":
            condition = args[0]
            return pd.Series(np.where(condition, args[1], args[2]), index=index, dtype="float64")
        if name in {"cross_sectional_rank", "group_neutralize"}:
            raise ValueError(f"{name} requires panel context and is not valid in a single-instrument run")
        raise ValueError(f"Unsupported factor function: {name}")

    result = _series(visit(node), index)
    return result.replace([np.inf, -np.inf], np.nan)
