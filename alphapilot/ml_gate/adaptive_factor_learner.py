"""Adaptive factor learner for research-only walk-forward rule discovery.

The learner is intentionally lightweight and auditable. It does not depend on
external ML packages, does not download data, does not use API keys, does not
read accounts, and does not create orders. It learns simple train-only factor
threshold rules and validates them on later time slices.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from alphapilot.factors.alpha101_style_overlay import ALPHA101_STYLE_FACTOR_COLUMNS
from alphapilot.ml_gate.probability_gate import evaluate_trades


ADAPTIVE_FACTOR_COLUMNS = [
    "rsi14",
    "return_3",
    "return_6",
    "return_12",
    "volume_ratio",
    "bollinger_z",
    "close_location",
    "atr_pct",
    "mark_basis_pct",
    "funding_z_60",
    "btc_return_3",
    "btc_return_6",
    "btc_return_12",
    "relative_return_6",
    "support_distance_pct",
    "resistance_distance_pct",
    *ALPHA101_STYLE_FACTOR_COLUMNS,
]


@dataclass(frozen=True)
class AdaptiveFactorLearnerConfig:
    folds: int = 4
    train_start_pct: float = 0.45
    max_rules_per_fold: int = 8
    min_train_events: int = 100
    min_rule_train_events: int = 35
    min_valid_factor_coverage_pct: float = 55.0
    quantiles: tuple[float, ...] = (0.15, 0.25, 0.75, 0.85)
    min_train_profit_factor: float = 1.25
    min_train_win_rate_pct: float = 42.0
    min_train_total_return_pct: float = 0.0


def _empty_result(config: AdaptiveFactorLearnerConfig) -> dict[str, Any]:
    return {
        "config": asdict(config),
        "foldSummaries": [],
        "learnedRules": [],
        "rulePerformance": [],
        "selectedEvents": pd.DataFrame(),
        "selectedMetrics": evaluate_trades(pd.DataFrame()),
        "baselineTestMetrics": evaluate_trades(pd.DataFrame()),
    }


def _rule_signature(context_label: str, column: str, operator: str, threshold: float, quantile: float) -> str:
    return f"{context_label}|{column}:{operator}:{threshold:.8g}:q{quantile:.2f}"


def _apply_rule(frame: pd.DataFrame, rule: dict[str, Any]) -> pd.Series:
    column = rule["factor"]
    if frame.empty or column not in frame.columns:
        return pd.Series([False] * len(frame), index=frame.index)
    context_mask = pd.Series([True] * len(frame), index=frame.index)
    for context_column, context_value in (rule.get("context") or {}).items():
        if context_column not in frame.columns:
            return pd.Series([False] * len(frame), index=frame.index)
        context_mask = context_mask & (frame[context_column].astype(str) == str(context_value))
    values = pd.to_numeric(frame[column], errors="coerce")
    threshold = float(rule["threshold"])
    if rule["operator"] == "<=":
        return context_mask & (values <= threshold)
    return context_mask & (values >= threshold)


def _score_metrics(metrics: dict[str, Any]) -> float:
    trade_count = float(metrics.get("tradeCount") or 0)
    win_rate = float(metrics.get("winRatePct") or 0)
    profit_factor = float(metrics.get("profitFactor") or 0)
    reward_risk = float(metrics.get("rewardRiskRatio") or 0)
    drawdown = float(metrics.get("maxDrawdownPct") or 999)
    total_return = float(metrics.get("totalReturnPct") or 0)
    return (
        min(profit_factor, 6.0) * 3.0
        + min(reward_risk, 3.0) * 1.5
        + min(win_rate, 80.0) / 20.0
        + np.log1p(max(trade_count, 0.0)) / 2.0
        + max(min(total_return, 500.0), -100.0) / 200.0
        - min(drawdown, 120.0) / 30.0
    )


def _factor_coverage(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").notna().mean() * 100)


def _context_candidates(train: pd.DataFrame, min_events: int) -> list[dict[str, Any]]:
    contexts: list[dict[str, Any]] = [{"contextLabel": "all", "context": {}, "frame": train}]
    for column in ["direction", "setupName", "btc_regime"]:
        if column not in train.columns:
            continue
        for value, group in train.groupby(column, dropna=False):
            if len(group) >= min_events:
                label = f"{column}={value}"
                contexts.append({"contextLabel": label, "context": {column: str(value)}, "frame": group})
    if "setupName" in train.columns and "btc_regime" in train.columns:
        for (setup, regime), group in train.groupby(["setupName", "btc_regime"], dropna=False):
            if len(group) >= max(min_events * 2, 80):
                label = f"setupName={setup};btc_regime={regime}"
                contexts.append(
                    {
                        "contextLabel": label,
                        "context": {"setupName": str(setup), "btc_regime": str(regime)},
                        "frame": group,
                    }
                )
    return contexts


def _discover_rules(
    train: pd.DataFrame,
    factor_columns: list[str],
    config: AdaptiveFactorLearnerConfig,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if train.empty:
        return candidates

    for context_item in _context_candidates(train, config.min_rule_train_events):
        context_frame = context_item["frame"]
        context_label = context_item["contextLabel"]
        context = context_item["context"]
        for column in factor_columns:
            if column not in context_frame.columns:
                continue
            coverage_pct = _factor_coverage(context_frame, column)
            if coverage_pct < config.min_valid_factor_coverage_pct:
                continue
            values = pd.to_numeric(context_frame[column], errors="coerce")
            if values.nunique(dropna=True) < 8:
                continue
            for quantile in config.quantiles:
                threshold = values.quantile(quantile)
                if not np.isfinite(threshold):
                    continue
                operator = "<=" if quantile <= 0.5 else ">="
                mask = values <= threshold if operator == "<=" else values >= threshold
                selected = context_frame[mask.fillna(False)].copy()
                metrics = evaluate_trades(selected)
                if (metrics.get("tradeCount") or 0) < config.min_rule_train_events:
                    continue
                if (metrics.get("profitFactor") or 0) < config.min_train_profit_factor:
                    continue
                if (metrics.get("winRatePct") or 0) < config.min_train_win_rate_pct:
                    continue
                if (metrics.get("totalReturnPct") or 0) <= config.min_train_total_return_pct:
                    continue
                signature = _rule_signature(context_label, column, operator, float(threshold), float(quantile))
                candidates.append(
                    {
                        "ruleSignature": signature,
                        "contextLabel": context_label,
                        "context": context,
                        "factor": column,
                        "operator": operator,
                        "threshold": round(float(threshold), 10),
                        "quantile": float(quantile),
                        "trainCoveragePct": round(coverage_pct, 4),
                        "trainMetrics": metrics,
                        "trainScore": round(float(_score_metrics(metrics)), 6),
                    }
                )

    return sorted(
        candidates,
        key=lambda item: (
            item["trainScore"],
            item["trainMetrics"].get("profitFactor") or 0,
            item["trainMetrics"].get("tradeCount") or 0,
        ),
        reverse=True,
    )[: config.max_rules_per_fold]


def _split_boundaries(row_count: int, train_start_pct: float, folds: int) -> list[tuple[int, int, int]]:
    start = int(row_count * train_start_pct)
    if folds <= 0 or row_count <= start:
        return []
    edges = np.linspace(start, row_count, folds + 1).astype(int)
    return [(0, int(edges[index]), int(edges[index + 1])) for index in range(folds) if edges[index + 1] > edges[index]]


def learn_adaptive_factor_rules(
    events: pd.DataFrame,
    factor_columns: list[str] | None = None,
    config: AdaptiveFactorLearnerConfig | None = None,
) -> dict[str, Any]:
    """Learn train-only factor threshold rules and validate on future folds."""

    active_config = config or AdaptiveFactorLearnerConfig()
    if events.empty:
        return _empty_result(active_config)

    usable_factors = factor_columns or ADAPTIVE_FACTOR_COLUMNS
    ordered = events.sort_values("signalDate").reset_index(drop=True).copy()
    if len(ordered) < active_config.min_train_events + active_config.min_rule_train_events:
        return _empty_result(active_config)

    selected_frames: list[pd.DataFrame] = []
    baseline_test_frames: list[pd.DataFrame] = []
    fold_summaries: list[dict[str, Any]] = []
    learned_rules: list[dict[str, Any]] = []
    rule_test_frames: dict[str, list[pd.DataFrame]] = {}

    for fold_index, (train_start, test_start, test_end) in enumerate(
        _split_boundaries(len(ordered), active_config.train_start_pct, active_config.folds)
    ):
        train = ordered.iloc[train_start:test_start].copy()
        test = ordered.iloc[test_start:test_end].copy()
        if len(train) < active_config.min_train_events or test.empty:
            continue
        rules = _discover_rules(train, usable_factors, active_config)
        baseline_test_frames.append(test)
        if not rules:
            fold_summaries.append(
                {
                    "fold": fold_index,
                    "trainRows": int(len(train)),
                    "testRows": int(len(test)),
                    "ruleCount": 0,
                    "testSelectedRows": 0,
                    "testMetrics": evaluate_trades(pd.DataFrame()),
                    "rules": [],
                }
            )
            continue

        combined_mask = pd.Series([False] * len(test), index=test.index)
        rule_hits = [[] for _ in range(len(test))]
        for rule in rules:
            rule = {**rule, "fold": fold_index}
            learned_rules.append(rule)
            mask = _apply_rule(test, rule).fillna(False)
            rule_selected = test[mask].copy()
            if not rule_selected.empty:
                rule_selected["adaptiveFold"] = fold_index
                rule_selected["matchedAdaptiveRule"] = rule["ruleSignature"]
                rule_test_frames.setdefault(rule["ruleSignature"], []).append(rule_selected)
            combined_mask = combined_mask | mask
            for position, passed in enumerate(mask.to_numpy()):
                if passed:
                    rule_hits[position].append(rule["ruleSignature"])

        selected = test[combined_mask].copy()
        if not selected.empty:
            selected["adaptiveFold"] = fold_index
            selected["adaptiveRuleHits"] = [rule_hits[pos] for pos, passed in enumerate(combined_mask.to_numpy()) if passed]
            selected["adaptiveRuleHitCount"] = selected["adaptiveRuleHits"].map(len)
            selected_frames.append(selected)

        fold_summaries.append(
            {
                "fold": fold_index,
                "trainRows": int(len(train)),
                "testRows": int(len(test)),
                "ruleCount": int(len(rules)),
                "testSelectedRows": int(len(selected)),
                "testMetrics": evaluate_trades(selected),
                "baselineTestMetrics": evaluate_trades(test),
                "rules": rules,
            }
        )

    selected_events = pd.concat(selected_frames, ignore_index=True) if selected_frames else pd.DataFrame()
    baseline_events = pd.concat(baseline_test_frames, ignore_index=True) if baseline_test_frames else pd.DataFrame()
    rule_performance: list[dict[str, Any]] = []
    for signature, frames in rule_test_frames.items():
        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        rule_meta = next((rule for rule in learned_rules if rule["ruleSignature"] == signature), {})
        rule_performance.append(
            {
                "ruleSignature": signature,
                "factor": rule_meta.get("factor"),
                "operator": rule_meta.get("operator"),
                "threshold": rule_meta.get("threshold"),
                "quantile": rule_meta.get("quantile"),
                "testMetrics": evaluate_trades(frame),
                "foldsMatched": sorted({int(item) for item in frame.get("adaptiveFold", pd.Series(dtype=int)).dropna().unique()}),
            }
        )
    rule_performance = sorted(
        rule_performance,
        key=lambda item: (
            item["testMetrics"].get("profitFactor") or 0,
            item["testMetrics"].get("tradeCount") or 0,
            item["testMetrics"].get("winRatePct") or 0,
        ),
        reverse=True,
    )
    return {
        "config": asdict(active_config),
        "foldSummaries": fold_summaries,
        "learnedRules": learned_rules,
        "rulePerformance": rule_performance,
        "selectedEvents": selected_events,
        "selectedMetrics": evaluate_trades(selected_events),
        "baselineTestMetrics": evaluate_trades(baseline_events),
    }
