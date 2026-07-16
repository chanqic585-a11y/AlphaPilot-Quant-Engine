"""Fail-closed compiler for the five frozen Advisory-R structure rules."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        raise ValueError(f"structure rule requires {column}")
    return pd.to_numeric(frame[column], errors="coerce")


def compile_structure_rule(
    candidate: Mapping[str, Any],
    frame: pd.DataFrame,
    *,
    side: int,
) -> pd.Series:
    """Return close-confirmed triggers; the exit engine executes on the next open."""

    policy = dict(candidate["exitPolicy"])
    parameters = dict(policy.get("parameters") or {})
    rule = dict(parameters.get("structureRule") or {})
    kind = str(rule.get("kind") or "")
    close = _numeric(frame, "close")

    if kind == "residual_neutral_zone":
        result = _numeric(frame, "residualZ").abs() <= float(
            rule["absoluteZscoreMaximum"]
        )
    elif kind == "event_reversal":
        confirmation_bars = int(rule["confirmationBars"])
        event_change = close.pct_change()
        opposite = event_change < 0 if side > 0 else event_change > 0
        result = (
            opposite.rolling(confirmation_bars, min_periods=confirmation_bars).sum()
            == confirmation_bars
        )
    elif kind == "correlation_recovery":
        result = _numeric(frame, "pairCorrelation") >= float(
            rule["minimumCorrelation"]
        )
    elif kind == "beta_rank_exit":
        rank = _numeric(frame, "betaRankPercentile")
        maximum = float(rule["maximumRankPercentile"])
        result = rank > maximum
    elif kind == "trend_invalidation":
        fast_window = int(rule["fastWindow"])
        slow_window = int(rule["slowWindow"])
        fast = close.rolling(fast_window, min_periods=fast_window).mean()
        slow = close.rolling(slow_window, min_periods=slow_window).mean()
        result = fast <= slow if side > 0 else fast >= slow
    else:
        raise ValueError(f"unsupported structure rule: {kind}")

    return pd.Series(result, index=frame.index).fillna(False).astype(bool)
