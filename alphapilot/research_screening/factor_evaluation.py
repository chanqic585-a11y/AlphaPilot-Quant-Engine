"""Bounded single-factor diagnostics with costs, folds, and concentration."""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd


def _row_spread(
    scores: np.ndarray,
    returns: np.ndarray,
    instruments: tuple[str, ...],
) -> tuple[float, dict[str, float], frozenset[str], frozenset[str]]:
    valid_positions = np.flatnonzero(np.isfinite(scores) & np.isfinite(returns))
    if len(valid_positions) < 4:
        return np.nan, {}, frozenset(), frozenset()
    count = max(1, int(len(valid_positions) * 0.2))
    ordered = valid_positions[np.argsort(scores[valid_positions], kind="stable")]
    bottom_positions = ordered[:count]
    top_positions = ordered[-count:]
    bottom = frozenset(instruments[position] for position in bottom_positions)
    top = frozenset(instruments[position] for position in top_positions)
    contributions = {
        instruments[position]: float(returns[position]) / count
        for position in top_positions
    }
    contributions.update(
        {
            instruments[position]: -float(returns[position]) / count
            for position in bottom_positions
        }
    )
    spread = float(returns[top_positions].mean() - returns[bottom_positions].mean())
    return spread, contributions, top, bottom


def _positive_concentration(values: dict[str, float]) -> float:
    positives = [value for value in values.values() if value > 0]
    return max(positives) / sum(positives) if positives else 0.0


def _p_value(samples: pd.Series) -> float:
    clean = samples.dropna()
    if len(clean) < 3 or clean.std(ddof=1) == 0:
        return 1.0
    z = abs(float(clean.mean() / (clean.std(ddof=1) / math.sqrt(len(clean)))))
    return float(2 * (1 - NormalDist().cdf(z)))


def evaluate_factor_trial(
    *,
    trial_id: str,
    factor: pd.DataFrame,
    forward_returns: pd.DataFrame,
    direction: int,
    base_cost_bps: float,
    folds: int,
    embargo_rows: int,
) -> dict[str, object]:
    if direction not in {-1, 1}:
        raise ValueError("direction must be -1 or 1")
    if folds < 2 or embargo_rows < 0:
        raise ValueError("invalid fold configuration")
    factor, forward_returns = factor.align(forward_returns, join="inner", axis=None)
    scores = factor * direction
    coverage = float((scores.notna() & forward_returns.notna()).sum().sum() / max(1, scores.size))
    rank_ic = scores.rank(axis=1, pct=True).corrwith(forward_returns.rank(axis=1, pct=True), axis=1)

    spreads: list[float] = []
    turnovers: list[float] = []
    instrument_pnl: dict[str, float] = {}
    previous_top: frozenset[str] = frozenset()
    previous_bottom: frozenset[str] = frozenset()
    instruments = tuple(str(column) for column in scores.columns)
    score_values = scores.to_numpy(dtype=float, copy=False)
    return_values = forward_returns.to_numpy(dtype=float, copy=False)
    for row_number in range(len(scores.index)):
        spread, contributions, top, bottom = _row_spread(
            score_values[row_number],
            return_values[row_number],
            instruments,
        )
        spreads.append(spread)
        for instrument, contribution in contributions.items():
            instrument_pnl[instrument] = instrument_pnl.get(instrument, 0.0) + contribution
        if previous_top or previous_bottom:
            changed = len(top.symmetric_difference(previous_top)) + len(bottom.symmetric_difference(previous_bottom))
            capacity = max(1, len(top) + len(bottom) + len(previous_top) + len(previous_bottom))
            turnovers.append(changed / capacity)
        else:
            turnovers.append(1.0 if top or bottom else np.nan)
        previous_top, previous_bottom = top, bottom

    gross = pd.Series(spreads, index=scores.index, dtype=float)
    turnover = pd.Series(turnovers, index=scores.index, dtype=float)
    base_net = gross - turnover * (base_cost_bps / 10_000)
    stress_net = gross - turnover * (base_cost_bps * 1.5 / 10_000)
    fold_rows: list[dict[str, object]] = []
    for number, indexes in enumerate(np.array_split(np.arange(len(base_net)), folds), start=1):
        usable = indexes[embargo_rows:] if number > 1 else indexes
        values = base_net.iloc[usable].dropna()
        fold_rows.append(
            {
                "foldId": f"fold_{number:03d}",
                "sampleCount": int(len(values)),
                "averageNetSpread": float(values.mean()) if len(values) else None,
                "positive": bool(len(values) and values.mean() > 0),
            }
        )
    month_pnl = base_net.groupby(base_net.index.strftime("%Y-%m")).sum(min_count=1).dropna()
    rank_clean = rank_ic.dropna()
    return {
        "trialId": trial_id,
        "direction": direction,
        "coverage": coverage,
        "missingRate": 1 - coverage,
        "rankICMean": float(rank_clean.mean()) if len(rank_clean) else None,
        "rankICStd": float(rank_clean.std(ddof=1)) if len(rank_clean) > 1 else None,
        "rankICIR": float(rank_clean.mean() / rank_clean.std(ddof=1)) if len(rank_clean) > 1 and rank_clean.std(ddof=1) else None,
        "rankICPositiveRatio": float((rank_clean > 0).mean()) if len(rank_clean) else None,
        "pValue": _p_value(rank_clean),
        "grossSpread": float(gross.mean(skipna=True)),
        "baseCostSpread": float(base_net.mean(skipna=True)),
        "stress1_5xSpread": float(stress_net.mean(skipna=True)),
        "turnover": float(turnover.mean(skipna=True)),
        "folds": fold_rows,
        "positiveFoldCount": sum(bool(item["positive"]) for item in fold_rows),
        "singleInstrumentPositiveContribution": _positive_concentration(instrument_pnl),
        "singleMonthPositiveContribution": _positive_concentration({str(key): float(value) for key, value in month_pnl.items()}),
        "instrumentContributions": dict(sorted(instrument_pnl.items())),
    }
