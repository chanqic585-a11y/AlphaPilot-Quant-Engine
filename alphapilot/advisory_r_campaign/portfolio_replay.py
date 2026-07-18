"""Capital-competing long/short portfolio replay for frozen S09."""

from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np
import pandas as pd

from alphapilot.exit_policy import exit_execution_to_dict, exit_policy_from_dict, replay_exit_policy

from .conformance import ImplementationConformanceError
from .structure_rules import compile_structure_rule


def _close_panel(frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    series: dict[str, pd.Series] = {}
    for symbol, raw in frames.items():
        frame = raw.copy()
        frame["date"] = pd.to_datetime(frame["date"], utc=True)
        if "confirmed" in frame:
            frame = frame[pd.to_numeric(frame["confirmed"], errors="coerce") == 1]
        series[symbol] = frame.sort_values("date").drop_duplicates("date", keep="last").set_index("date")["close"].astype(float)
    return pd.DataFrame(series).dropna().sort_index()


def _beta_panel(close: pd.DataFrame, window: int) -> pd.DataFrame:
    returns = close.pct_change()
    btc = returns["BTC-USDT-SWAP"]
    variance = btc.rolling(window, min_periods=window).var().replace(0, np.nan)
    return pd.DataFrame(
        {
            symbol: returns[symbol].rolling(window, min_periods=window).cov(btc) / variance
            for symbol in close.columns
            if symbol != "BTC-USDT-SWAP"
        }
    )


def _synthetic_portfolio(
    close: pd.DataFrame,
    *,
    long_symbols: list[str],
    short_symbols: list[str],
) -> pd.DataFrame:
    returns = close.pct_change().fillna(0.0)
    portfolio_return = 0.5 * returns[long_symbols].mean(axis=1) - 0.5 * returns[short_symbols].mean(axis=1)
    wealth = 100.0 * (1.0 + portfolio_return).cumprod()
    open_ = wealth.shift(1).fillna(wealth.iloc[0])
    return pd.DataFrame(
        {
            "date": close.index,
            "open": open_.to_numpy(),
            "high": pd.concat([open_, wealth], axis=1).max(axis=1).to_numpy(),
            "low": pd.concat([open_, wealth], axis=1).min(axis=1).to_numpy(),
            "close": wealth.to_numpy(),
            "volume": 1.0,
        }
    )


def replay_portfolio_candidate(
    candidate: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame],
    *,
    round_trip_cost_rate: float,
) -> list[dict[str, Any]]:
    if str(candidate["variantId"]) != "S09":
        raise ImplementationConformanceError("portfolio replay only supports frozen S09")
    close = _close_panel(frames)
    if "BTC-USDT-SWAP" not in close or len(close.columns) < 4:
        return []
    feature = dict(candidate["featureDefinition"])
    entry = dict(candidate["entryDefinition"])
    beta = _beta_panel(close, int(feature["betaWindow"]))
    ranks = beta.rank(axis=1, pct=True, method="average")
    btc_weak = close["BTC-USDT-SWAP"].pct_change(int(feature["btcTrendWindow"])) < 0
    rebalance_bars = int(feature["rebalanceBars"])
    long_fraction = float(entry["longQuantile"])
    short_fraction = float(entry["shortQuantile"])
    policy = exit_policy_from_dict(dict(candidate["exitPolicy"]))
    from .signals import _formal_costs

    events: list[dict[str, Any]] = []
    next_available = 0
    for signal_index in range(0, len(close) - 1, rebalance_bars):
        if signal_index < next_available or not bool(btc_weak.iloc[signal_index]):
            continue
        row = beta.iloc[signal_index].dropna().sort_values()
        if len(row) < 3:
            continue
        long_count = max(1, math.ceil(len(row) * long_fraction))
        short_count = max(1, math.ceil(len(row) * short_fraction))
        long_symbols = list(row.index[:long_count])
        short_symbols = list(row.index[-short_count:])
        short_symbols = [symbol for symbol in short_symbols if symbol not in long_symbols]
        if not short_symbols:
            continue
        synthetic = _synthetic_portfolio(
            close, long_symbols=long_symbols, short_symbols=short_symbols
        )
        long_rank = ranks[long_symbols].mean(axis=1)
        short_rank = ranks[short_symbols].mean(axis=1)
        synthetic["betaRankPercentile"] = pd.concat(
            [long_rank, 1.0 - short_rank], axis=1
        ).max(axis=1).to_numpy()
        risk_distance = (
            float(synthetic.iloc[signal_index + 1]["open"])
            * 0.01
            * float(dict(candidate["initialStopDefinition"])["riskBudgetR"])
        )
        structure = compile_structure_rule(candidate, synthetic, side=1)
        result = replay_exit_policy(
            frame=synthetic,
            signalPosition=signal_index,
            direction="long",
            riskDistance=risk_distance,
            policy=policy,
            costs=_formal_costs(round_trip_cost_rate),
            structureExitMask=structure,
            fundingRate=None,
        )
        if result.exitPolicyHash != str(candidate["exitPolicyHash"]):
            raise ImplementationConformanceError("portfolio exit-policy hash mismatch")
        payload = exit_execution_to_dict(result)
        payload.update(
            {
                "candidateId": candidate["candidateId"],
                "familyId": candidate["familyId"],
                "variantId": candidate["variantId"],
                "symbol": "PORTFOLIO",
                "longSymbols": long_symbols,
                "shortSymbols": short_symbols,
                "grossExposure": 1.0,
                "netExposure": 0.0,
                "rebalanceBars": rebalance_bars,
                "historicalPitAvailable": False,
                "fixedCohortBias": True,
                "signalIndex": result.signalPosition,
                "entryIndex": result.entryPosition,
                "exitIndex": result.exitPosition,
                "side": result.direction,
                "exitPrice": result.legs[-1].price,
                "targetR": policy.parameters.get("targetR"),
                "costR": result.feesR + result.slippageR + result.spreadProxyR,
                "realizedGrossR": result.grossR,
                "realizedNetR": result.netR,
                "exitReason": result.legs[-1].reason,
                "partialExit": len(result.legs) > 1,
                "profitGivebackR": result.givebackR,
                "exitPolicyMode": policy.mode.value,
                "maximumHold": policy.maximumHoldBars,
                "initialStopMayWiden": False,
                "fundingR": None,
            }
        )
        events.append(payload)
        next_available = result.exitPosition + 1
    return events
