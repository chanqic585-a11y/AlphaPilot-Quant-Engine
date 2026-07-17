"""Frozen BTC beta estimation and signed portfolio projection for V18."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash


BETA_POLICY_V1: dict[str, Any] = {
    "schemaVersion": "s01_portfolio_beta_policy_v1",
    "benchmark": "BTC-USDT-SWAP",
    "method": "ols_covariance_ratio_without_intercept_equivalent_slope",
    "returnDefinition": "utc_daily_log_return",
    "lookbackBars": 90,
    "minimumAlignedBars": 60,
    "alignment": "intersection_of_strictly_prior_utc_days",
    "benchmarkBeta": 1.0,
    "contributionFormula": "direction_sign_times_mark_notional_over_current_equity_times_beta",
    "maximumAbsoluteProjectedBeta": 1.5,
    "missingDataPolicy": "reject_candidate",
    "zeroBenchmarkVariancePolicy": "reject_candidate",
    "varianceEpsilon": 1e-18,
}
BETA_POLICY_V1["definitionHash"] = stable_hash(
    BETA_POLICY_V1, prefix="s01_portfolio_beta_policy_v1"
)


def _utc(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _series(
    rows: Sequence[Mapping[str, Any]], as_of: datetime
) -> dict[object, float]:
    values: dict[object, float] = {}
    for row in rows:
        try:
            timestamp = _utc(row.get("timestamp"))
            value = float(row.get("return"))
        except (TypeError, ValueError):
            continue
        if timestamp.date() >= as_of.date() or not math.isfinite(value):
            continue
        values[timestamp.date()] = value
    return {day: values[day] for day in sorted(values)[-90:]}


def estimate_portfolio_betas_v1(
    return_panel: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    as_of_timestamp: str,
    benchmark: str = "BTC-USDT-SWAP",
) -> dict[str, Any]:
    as_of = _utc(as_of_timestamp)
    benchmark_series = _series(return_panel.get(benchmark, []), as_of)
    betas: dict[str, float] = {}
    rejected: dict[str, str] = {}
    for symbol in sorted(str(key) for key in return_panel):
        series = _series(return_panel[symbol], as_of)
        overlap = sorted(set(benchmark_series) & set(series))
        if len(overlap) < int(BETA_POLICY_V1["minimumAlignedBars"]):
            rejected[symbol] = "insufficient_aligned_history"
            continue
        if symbol == benchmark:
            betas[symbol] = 1.0
            continue
        benchmark_values = [benchmark_series[day] for day in overlap]
        values = [series[day] for day in overlap]
        benchmark_mean = sum(benchmark_values) / len(benchmark_values)
        value_mean = sum(values) / len(values)
        variance = sum((value - benchmark_mean) ** 2 for value in benchmark_values)
        if variance <= float(BETA_POLICY_V1["varianceEpsilon"]):
            rejected[symbol] = "benchmark_variance_below_epsilon"
            continue
        covariance = sum(
            (benchmark_values[index] - benchmark_mean) * (values[index] - value_mean)
            for index in range(len(overlap))
        )
        betas[symbol] = covariance / variance
    return {
        "schemaVersion": BETA_POLICY_V1["schemaVersion"],
        "benchmark": benchmark,
        "betas": dict(sorted(betas.items())),
        "rejected": dict(sorted(rejected.items())),
        "asOf": as_of.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lookaheadReadCount": 0,
        "betaPolicyHash": BETA_POLICY_V1["definitionHash"],
    }


def _direction_sign(direction: object) -> float:
    normalized = str(direction).lower()
    if normalized in {"long", "buy"}:
        return 1.0
    if normalized in {"short", "sell"}:
        return -1.0
    raise ValueError(f"Unsupported position direction: {direction}")


def _contribution(position: Mapping[str, Any], current_equity: float) -> float:
    notional = float(position["markNotional"])
    beta = float(position["beta"])
    if not all(math.isfinite(value) for value in (notional, beta)) or notional < 0.0:
        raise ValueError("Position markNotional and beta must be finite")
    return _direction_sign(position["direction"]) * notional / current_equity * beta


def project_portfolio_beta_v1(
    *,
    open_positions: Sequence[Mapping[str, Any]],
    candidate: Mapping[str, Any],
    current_equity: float,
) -> dict[str, Any]:
    equity = float(current_equity)
    if not math.isfinite(equity) or equity <= 0.0:
        raise ValueError("current_equity must be positive and finite")
    current = sum(_contribution(position, equity) for position in open_positions)
    candidate_contribution = _contribution(candidate, equity)
    projected = current + candidate_contribution
    return {
        "currentPortfolioBeta": current,
        "candidateContribution": candidate_contribution,
        "projectedPortfolioBeta": projected,
        "betaPassed": abs(projected)
        <= float(BETA_POLICY_V1["maximumAbsoluteProjectedBeta"]) + 1e-12,
        "betaPolicyHash": BETA_POLICY_V1["definitionHash"],
    }
