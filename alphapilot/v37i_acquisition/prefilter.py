"""Causal development-only prefilters for V37I candidates."""

from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from .catalog import CandidateSpec


def development_slice(
    frame: pd.DataFrame, *, development_fraction: float = 0.8
) -> tuple[pd.DataFrame, dict[str, int]]:
    if not 0.5 <= development_fraction < 1.0:
        raise ValueError("development_fraction_out_of_bounds")
    split = max(1, int(len(frame) * development_fraction))
    development = frame.iloc[:split].copy()
    return development, {
        "totalRowCount": int(len(frame)),
        "developmentRowCount": int(len(development)),
        "reservedLockedOosRowCount": int(len(frame) - len(development)),
        "lockedOosReadCount": 0,
    }


def summarize_trial(
    *,
    trade_returns: Iterable[float],
    bar_returns: Iterable[float],
    transaction_cost: float,
) -> dict[str, float | int | None]:
    trades = np.asarray(list(trade_returns), dtype=float)
    bars = np.asarray(list(bar_returns), dtype=float)
    positive = float(trades[trades > 0].sum()) if len(trades) else 0.0
    negative = float(-trades[trades < 0].sum()) if len(trades) else 0.0
    profit_factor = positive / negative if negative > 0 else (None if positive == 0 else 999.0)
    curve = np.concatenate(([0.0], np.cumsum(bars))) if len(bars) else np.asarray([0.0])
    maximum_drawdown = float(np.max(np.maximum.accumulate(curve) - curve))
    return {
        "tradeCount": int(len(trades)),
        "netReturn": float(trades.sum()) if len(trades) else 0.0,
        "averageNetReturn": float(trades.mean()) if len(trades) else None,
        "profitFactor": profit_factor,
        "maximumDrawdown": maximum_drawdown,
        "transactionCost": float(transaction_cost),
    }


def load_development_panels(
    panel_manifest: Mapping[str, Any], *, development_fraction: float = 0.8
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    panels: dict[str, pd.DataFrame] = {}
    audits: dict[str, Any] = {}
    for artifact in panel_manifest.get("panelArtifacts") or []:
        asset = str(artifact.get("asset") or "").strip()
        path = Path(str(artifact.get("path") or ""))
        if not asset or not path.is_file():
            raise FileNotFoundError(f"v37i_panel_missing:{asset}:{path}")
        frame = pd.read_parquet(path).sort_values("decisionTimestampMs").reset_index(drop=True)
        required = {
            "decisionTimestampMs",
            "fundingRate",
            "spotPrice",
            "perpetualPrice",
            "basisPct",
            "dualLegQuoteTurnoverProxy",
        }
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"v37i_panel_columns_missing:{asset}:{','.join(missing)}")
        development, audit = development_slice(
            frame, development_fraction=development_fraction
        )
        panels[asset] = development
        audits[asset] = audit
    if set(panels) != {"BTC", "ETH", "SOL"}:
        raise ValueError("v37i_funding_universe_incomplete")
    return panels, {
        "perAsset": audits,
        "lockedOosReadCount": 0,
        "developmentFraction": development_fraction,
    }


def _next_delta_neutral_return(frame: pd.DataFrame, index: int) -> float:
    spot_return = float(frame.iloc[index + 1]["spotPrice"]) / float(
        frame.iloc[index]["spotPrice"]
    ) - 1.0
    perpetual_return = float(frame.iloc[index + 1]["perpetualPrice"]) / float(
        frame.iloc[index]["perpetualPrice"]
    ) - 1.0
    next_funding = float(frame.iloc[index + 1]["fundingRate"])
    return spot_return - perpetual_return + next_funding


def _funding_carry_trial(
    panels: Mapping[str, pd.DataFrame], parameters: Mapping[str, Any]
) -> dict[str, Any]:
    enter = float(parameters["enterFunding"])
    exit_rate = float(parameters["exitFunding"])
    basis_cap = float(parameters["basisCapPct"])
    minimum_turnover = float(parameters["minimumTurnover"])
    half_cost = float(parameters["costBps"]) / 10_000.0 / 2.0
    all_trades: list[float] = []
    all_bars: list[float] = []
    profitable_assets = 0
    total_cost = 0.0
    per_asset: dict[str, Any] = {}
    for asset, frame in panels.items():
        open_position = False
        current_trade = 0.0
        asset_trades: list[float] = []
        asset_bars: list[float] = []
        for index in range(len(frame) - 1):
            row = frame.iloc[index]
            valid_entry = (
                float(row["fundingRate"]) >= enter
                and abs(float(row["basisPct"])) <= basis_cap
                and float(row["dualLegQuoteTurnoverProxy"]) >= minimum_turnover
            )
            should_exit = open_position and (
                float(row["fundingRate"]) <= exit_rate
                or abs(float(row["basisPct"])) > basis_cap * 1.5
            )
            if should_exit:
                current_trade -= half_cost
                total_cost += half_cost
                asset_trades.append(current_trade)
                current_trade = 0.0
                open_position = False
            if not open_position and valid_entry:
                open_position = True
                current_trade = -half_cost
                total_cost += half_cost
            bar_return = 0.0
            if open_position:
                bar_return = _next_delta_neutral_return(frame, index)
                current_trade += bar_return
            asset_bars.append(bar_return)
        if open_position:
            current_trade -= half_cost
            total_cost += half_cost
            asset_trades.append(current_trade)
        if sum(asset_trades) > 0:
            profitable_assets += 1
        all_trades.extend(asset_trades)
        all_bars.extend(asset_bars)
        per_asset[asset] = summarize_trial(
            trade_returns=asset_trades,
            bar_returns=asset_bars,
            transaction_cost=0.0,
        )
    return {
        **summarize_trial(
            trade_returns=all_trades,
            bar_returns=all_bars,
            transaction_cost=total_cost,
        ),
        "profitableAssetCount": profitable_assets,
        "perAsset": per_asset,
    }


def _funding_event_trial(
    panels: Mapping[str, pd.DataFrame], parameters: Mapping[str, Any]
) -> dict[str, Any]:
    window = int(parameters["baselineBars"])
    threshold = float(parameters["surpriseZ"])
    basis_cap = float(parameters["basisCapPct"])
    round_trip_cost = float(parameters["costBps"]) / 10_000.0
    trades: list[float] = []
    bars: list[float] = []
    profitable_assets = 0
    total_cost = 0.0
    for frame in panels.values():
        history = frame["fundingRate"].shift(1)
        median = history.rolling(window).median()
        scale = history.rolling(window).std()
        surprise = (frame["fundingRate"] - median) / scale.replace(0.0, np.nan)
        asset_trades: list[float] = []
        for index in range(window, len(frame) - 1):
            if (
                pd.notna(surprise.iloc[index])
                and float(surprise.iloc[index]) >= threshold
                and abs(float(frame.iloc[index]["basisPct"])) <= basis_cap
            ):
                result = _next_delta_neutral_return(frame, index) - round_trip_cost
                trades.append(result)
                asset_trades.append(result)
                bars.append(result)
                total_cost += round_trip_cost
            else:
                bars.append(0.0)
        if sum(asset_trades) > 0:
            profitable_assets += 1
    return {
        **summarize_trial(
            trade_returns=trades,
            bar_returns=bars,
            transaction_cost=total_cost,
        ),
        "profitableAssetCount": profitable_assets,
    }


def _pair_relative_value_trial(
    panels: Mapping[str, pd.DataFrame], parameters: Mapping[str, Any]
) -> dict[str, Any]:
    formation = int(parameters["formationBars"])
    entry_z = float(parameters["entryZ"])
    max_hold = int(parameters["maximumHoldBars"])
    half_cost = float(parameters["costBps"]) / 10_000.0 / 2.0
    prices = {
        asset: frame["spotPrice"].reset_index(drop=True).astype(float)
        for asset, frame in panels.items()
    }
    minimum_rows = min(len(value) for value in prices.values())
    pair_scores: list[tuple[float, str, str]] = []
    for left, right in combinations(sorted(prices), 2):
        left_path = prices[left].iloc[:formation] / prices[left].iloc[0]
        right_path = prices[right].iloc[:formation] / prices[right].iloc[0]
        pair_scores.append((float(((left_path - right_path) ** 2).mean()), left, right))
    _, left, right = min(pair_scores)
    spread = np.log(prices[left].iloc[:minimum_rows]) - np.log(
        prices[right].iloc[:minimum_rows]
    )
    mean = spread.shift(1).rolling(formation).mean()
    scale = spread.shift(1).rolling(formation).std().replace(0.0, np.nan)
    zscore = (spread - mean) / scale
    position = 0
    hold = 0
    current_trade = 0.0
    total_cost = 0.0
    trades: list[float] = []
    bars: list[float] = []
    for index in range(formation, minimum_rows - 1):
        z_value = float(zscore.iloc[index]) if pd.notna(zscore.iloc[index]) else 0.0
        if position == 0:
            if z_value >= entry_z:
                position = -1
            elif z_value <= -entry_z:
                position = 1
            if position:
                current_trade = -half_cost
                total_cost += half_cost
                hold = 0
        bar_return = 0.0
        if position:
            pair_return = (
                float(prices[left].iloc[index + 1]) / float(prices[left].iloc[index])
                - float(prices[right].iloc[index + 1]) / float(prices[right].iloc[index])
            )
            bar_return = position * pair_return
            current_trade += bar_return
            hold += 1
            mean_crossed = (position > 0 and z_value >= 0.0) or (
                position < 0 and z_value <= 0.0
            )
            if mean_crossed or hold >= max_hold:
                current_trade -= half_cost
                total_cost += half_cost
                trades.append(current_trade)
                bar_return -= half_cost
                position = 0
                hold = 0
                current_trade = 0.0
        bars.append(bar_return)
    if position:
        current_trade -= half_cost
        total_cost += half_cost
        trades.append(current_trade)
    return {
        **summarize_trial(
            trade_returns=trades,
            bar_returns=bars,
            transaction_cost=total_cost,
        ),
        "selectedPair": [left, right],
        "profitableAssetCount": 0,
    }


def evaluate_candidate(
    spec: CandidateSpec, panels: Mapping[str, pd.DataFrame]
) -> dict[str, Any]:
    if spec.prefilter_blocker:
        return {
            "candidateId": spec.candidate_id,
            "candidateHash": spec.candidate_hash,
            "campaignId": spec.campaign_id,
            "familyId": spec.family_id,
            "prefilterPassed": False,
            "status": "prefilter_failed",
            "reasonCode": spec.prefilter_blocker,
            "trialCount": 0,
            "passedTrialCount": 0,
            "lockedOosReadCount": 0,
            "trials": [],
        }
    runner = (
        _funding_carry_trial
        if spec.family_id == "crypto_funding_carry_v1"
        else (
            _pair_relative_value_trial
            if spec.family_id == "crypto_pair_relative_value_v2"
            else _funding_event_trial
        )
    )
    trials: list[dict[str, Any]] = []
    for index, parameters in enumerate(spec.parameter_trials, start=1):
        metrics = runner(panels, parameters)
        profit_factor = metrics.get("profitFactor")
        minimum_trades = 20 if spec.family_id == "crypto_pair_relative_value_v2" else 30
        passed = (
            int(metrics["tradeCount"]) >= minimum_trades
            and float(metrics["netReturn"]) > 0.0
            and profit_factor is not None
            and float(profit_factor) >= 1.10
            and float(metrics["maximumDrawdown"]) <= 0.25
        )
        trials.append(
            {
                "trialIndex": index,
                "parameters": dict(parameters),
                "metrics": metrics,
                "passed": passed,
            }
        )
    passed_trials = [trial for trial in trials if trial["passed"]]
    passed = len(passed_trials) >= 2
    best = max(
        trials,
        key=lambda trial: float(trial["metrics"].get("netReturn") or 0.0),
    )
    return {
        "candidateId": spec.candidate_id,
        "candidateHash": spec.candidate_hash,
        "campaignId": spec.campaign_id,
        "familyId": spec.family_id,
        "prefilterPassed": passed,
        "status": "research_pass" if passed else "prefilter_failed",
        "reasonCode": "stable_parameter_neighborhood" if passed else "economic_prefilter_failed",
        "trialCount": len(trials),
        "passedTrialCount": len(passed_trials),
        "selectedTrialIndex": int(best["trialIndex"]) if passed else None,
        "bestNetReturn": float(best["metrics"].get("netReturn") or 0.0),
        "bestProfitFactor": best["metrics"].get("profitFactor"),
        "bestMaximumDrawdown": float(best["metrics"].get("maximumDrawdown") or 0.0),
        "bestTradeCount": int(best["metrics"].get("tradeCount") or 0),
        "lockedOosReadCount": 0,
        "trials": trials,
    }
