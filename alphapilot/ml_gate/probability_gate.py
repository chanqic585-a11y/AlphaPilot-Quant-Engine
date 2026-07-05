"""Walk-forward probability gate for V13.5 research candidates.

This module deliberately uses simple train-only probability buckets instead of
external ML packages. It gives AlphaPilot a reproducible probability gate while
keeping the first executable version easy to audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ProbabilityGateConfig:
    train_min_events: int = 80
    min_bucket_events: int = 8
    probability_threshold: float = 0.57
    min_score_components: int = 4


FEATURE_BUCKETS = {
    "rsi14": [30, 40, 50, 60, 70],
    "return_3": [-0.06, -0.035, -0.015, 0.0, 0.015, 0.035, 0.06],
    "volume_ratio": [0.7, 1.0, 1.3, 1.8, 2.5],
    "bollinger_z": [-2.0, -1.2, -0.5, 0.5, 1.2, 2.0],
    "funding_z_60": [-1.5, -0.8, -0.2, 0.2, 0.8, 1.5],
    "mark_basis_pct": [-0.002, -0.0008, -0.0002, 0.0002, 0.0008, 0.002],
    "btc_return_3": [-0.06, -0.03, -0.01, 0.01, 0.03, 0.06],
    "relative_return_6": [-0.08, -0.03, -0.01, 0.01, 0.03, 0.08],
    "atr_pct": [0.01, 0.02, 0.035, 0.055, 0.08],
}


def _bucket_value(value: Any, edges: list[float]) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "missing"
    if not np.isfinite(numeric):
        return "missing"
    index = int(np.searchsorted(edges, numeric, side="right"))
    if index == 0:
        return f"<= {edges[0]}"
    if index >= len(edges):
        return f"> {edges[-1]}"
    return f"({edges[index - 1]}, {edges[index]}]"


def add_probability_buckets(events: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    for column, edges in FEATURE_BUCKETS.items():
        out[f"bucket_{column}"] = out[column].map(lambda value, e=edges: _bucket_value(value, e))
    out["bucket_btc_regime"] = out["btc_regime"].fillna("missing").astype(str)
    out["bucket_setupName"] = out["setupName"].fillna("missing").astype(str)
    out["bucket_pair"] = out["pair"].fillna("missing").astype(str)
    return out


def _bucket_stats(train: pd.DataFrame, column: str, min_bucket_events: int) -> dict[str, tuple[int, float]]:
    stats: dict[str, tuple[int, float]] = {}
    for value, group in train.groupby(column, dropna=False):
        count = len(group)
        if count < min_bucket_events:
            continue
        wins = int(group["isWin"].sum())
        # Laplace smoothing keeps tiny samples from overclaiming certainty.
        win_rate = (wins + 1) / (count + 2)
        stats[str(value)] = (count, float(win_rate))
    return stats


def _score_row(
    row: pd.Series,
    bucket_tables: dict[str, dict[str, tuple[int, float]]],
    global_win_rate: float,
) -> tuple[float, int, list[dict[str, Any]]]:
    weighted_score = 0.0
    total_weight = 0.0
    components: list[dict[str, Any]] = []
    for column, table in bucket_tables.items():
        value = str(row.get(column, "missing"))
        if value not in table:
            continue
        count, win_rate = table[value]
        weight = min(3.0, np.log1p(count) / 2.0)
        weighted_score += win_rate * weight
        total_weight += weight
        components.append(
            {
                "bucketColumn": column,
                "bucketValue": value,
                "trainCount": count,
                "bucketWinRate": round(win_rate * 100, 4),
                "weight": round(float(weight), 4),
            }
        )
    if total_weight <= 0:
        return global_win_rate, 0, components
    return float(weighted_score / total_weight), len(components), components


def apply_walk_forward_probability_gate(
    events: pd.DataFrame,
    config: ProbabilityGateConfig,
    folds: int = 5,
) -> pd.DataFrame:
    if events.empty:
        return events.copy()
    prepared = add_probability_buckets(events).sort_values("signalDate").reset_index(drop=True)
    prepared["probabilityScore"] = np.nan
    prepared["probabilityComponents"] = 0
    prepared["probabilityGatePassed"] = False
    prepared["probabilityEvidence"] = [[] for _ in range(len(prepared))]
    prepared["walkForwardFold"] = -1

    if len(prepared) < config.train_min_events + 10:
        return prepared

    boundaries = np.linspace(0.35, 1.0, folds + 1)
    row_count = len(prepared)
    bucket_columns = [
        "bucket_setupName",
        "bucket_pair",
        "bucket_btc_regime",
        *[f"bucket_{name}" for name in FEATURE_BUCKETS],
    ]

    for fold_index in range(folds):
        test_start = int(row_count * boundaries[fold_index])
        test_end = int(row_count * boundaries[fold_index + 1])
        if test_end <= test_start:
            continue
        train = prepared.iloc[:test_start]
        test_index = prepared.index[test_start:test_end]
        if len(train) < config.train_min_events:
            continue
        global_win_rate = float((train["isWin"].sum() + 1) / (len(train) + 2))
        bucket_tables = {
            column: _bucket_stats(train, column, config.min_bucket_events)
            for column in bucket_columns
        }
        for idx in test_index:
            score, component_count, evidence = _score_row(prepared.loc[idx], bucket_tables, global_win_rate)
            prepared.at[idx, "probabilityScore"] = round(score, 6)
            prepared.at[idx, "probabilityComponents"] = component_count
            prepared.at[idx, "probabilityGatePassed"] = bool(
                score >= config.probability_threshold
                and component_count >= config.min_score_components
            )
            prepared.at[idx, "probabilityEvidence"] = evidence[:8]
            prepared.at[idx, "walkForwardFold"] = fold_index
    return prepared


def evaluate_trades(trades: pd.DataFrame) -> dict[str, Any]:
    if trades.empty:
        return {
            "tradeCount": 0,
            "winRatePct": None,
            "averageWinPct": None,
            "averageLossPct": None,
            "rewardRiskRatio": None,
            "profitFactor": None,
            "totalReturnPct": 0.0,
            "maxDrawdownPct": 0.0,
            "researchWorthContinuing": False,
        }
    returns = trades["netReturnPct"].astype(float)
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    equity = (1 + returns / 100).cumprod()
    peak = equity.cummax()
    drawdown = (peak - equity) / peak.replace(0, np.nan)
    average_win = float(wins.mean()) if len(wins) else None
    average_loss = float(losses.mean()) if len(losses) else None
    reward_risk = (average_win / abs(average_loss)) if average_win is not None and average_loss and average_loss < 0 else None
    profit_factor = (wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else None
    total_return = float((equity.iloc[-1] - 1) * 100)
    max_drawdown = float(drawdown.max() * 100) if len(drawdown) else 0.0
    win_rate = float(len(wins) / len(returns) * 100)
    research_worth = bool(
        len(returns) >= 100
        and win_rate >= 55
        and reward_risk is not None
        and reward_risk >= 1.8
        and profit_factor is not None
        and profit_factor >= 1.35
        and max_drawdown <= 20
        and total_return > 0
    )
    return {
        "tradeCount": int(len(returns)),
        "winRatePct": round(win_rate, 4),
        "averageWinPct": round(average_win, 6) if average_win is not None else None,
        "averageLossPct": round(average_loss, 6) if average_loss is not None else None,
        "rewardRiskRatio": round(reward_risk, 4) if reward_risk is not None else None,
        "profitFactor": round(float(profit_factor), 4) if profit_factor is not None else None,
        "totalReturnPct": round(total_return, 4),
        "maxDrawdownPct": round(max_drawdown, 4),
        "researchWorthContinuing": research_worth,
    }
