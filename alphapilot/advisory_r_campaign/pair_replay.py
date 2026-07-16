"""Causal two-leg replay for frozen Advisory-R relative-value candidates."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from alphapilot.exit_policy import (
    exit_execution_to_dict,
    exit_policy_from_dict,
    replay_exit_policy,
)

from .conformance import ImplementationConformanceError
from .structure_rules import compile_structure_rule


def _ordered(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], utc=True)
    if "confirmed" in result:
        result = result[pd.to_numeric(result["confirmed"], errors="coerce") == 1]
    for column in ("open", "high", "low", "close", "volume"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def _rolling_z(values: pd.Series, window: int) -> pd.Series:
    mean = values.rolling(window, min_periods=window).mean()
    standard = values.rolling(window, min_periods=window).std(ddof=0).replace(0, np.nan)
    return (values - mean) / standard


def _atr(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    previous = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous).abs(),
            (frame["low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window, min_periods=window).mean()


def _costs(round_trip_cost_rate: float):
    from .signals import _formal_costs

    return _formal_costs(round_trip_cost_rate * 2.0)


def _aligned_pair(alt: pd.DataFrame, btc: pd.DataFrame) -> pd.DataFrame:
    columns = ["date", "open", "high", "low", "close", "volume"]
    return alt[columns].merge(
        btc[columns], on="date", how="inner", suffixes=("Alt", "Btc")
    ).sort_values("date").reset_index(drop=True)


def _pair_metrics(candidate: Mapping[str, Any], pair: pd.DataFrame) -> pd.DataFrame:
    feature = dict(candidate["featureDefinition"])
    variant = str(candidate["variantId"])
    window = int(feature.get("pairWindow") or feature.get("correlationWindow"))
    alt_return = pair["closeAlt"].pct_change()
    btc_return = pair["closeBtc"].pct_change()
    btc_variance = btc_return.rolling(window, min_periods=window).var().replace(0, np.nan)
    beta = alt_return.rolling(window, min_periods=window).cov(btc_return) / btc_variance
    residual = alt_return - beta * btc_return
    result = pair.copy()
    result["beta"] = beta
    result["residual"] = residual
    result["residualStd"] = residual.rolling(window, min_periods=window).std(ddof=0)
    result["residualZ"] = _rolling_z(residual, window)
    result["pairCorrelation"] = alt_return.rolling(window, min_periods=window).corr(btc_return)
    if variant in {"S05", "S06"}:
        turn_bars = int(dict(candidate["entryDefinition"]).get("residualTurnBars") or 1)
        result["correlationBaseline"] = (
            result["pairCorrelation"]
            .shift(turn_bars)
            .rolling(window, min_periods=window)
            .mean()
        )
    return result


def _signals(candidate: Mapping[str, Any], metrics: pd.DataFrame) -> pd.Series:
    feature = dict(candidate["featureDefinition"])
    entry = dict(candidate["entryDefinition"])
    variant = str(candidate["variantId"])
    direction = pd.Series(0, index=metrics.index, dtype="int64")
    if variant == "S04":
        z = metrics["residualZ"]
        extreme = z.abs() >= float(feature["entryResidualZ"])
        turn = z.abs() < z.abs().shift(1)
        condition = extreme & (metrics["pairCorrelation"] >= float(feature["minimumCorrelation"]))
        if bool(entry["requireTurn"]):
            condition &= turn
        direction.loc[condition.fillna(False)] = -np.sign(z[condition.fillna(False)]).astype(int)
    elif variant in {"S05", "S06"}:
        baseline = metrics["correlationBaseline"]
        baseline_minimum = float(feature.get("baselineMinimum", 0.75))
        broken = (baseline >= baseline_minimum) & (
            metrics["pairCorrelation"] <= float(feature["breakMaximum"])
        )
        if variant == "S05":
            bars = int(entry["residualTurnBars"])
            turning = metrics["residual"].abs().diff() < 0
            turning = turning.rolling(bars, min_periods=bars).sum() == bars
            condition = broken & turning
            direction.loc[condition.fillna(False)] = -np.sign(
                metrics.loc[condition.fillna(False), "residual"]
            ).astype(int)
        else:
            bars = int(feature["relativeStrengthBars"])
            strength = metrics["residual"].rolling(bars, min_periods=bars).sum()
            strength_z = _rolling_z(strength, int(feature["correlationWindow"]))
            condition = broken & (strength_z.abs() >= float(entry["minimumRelativeMoveZ"]))
            direction.loc[condition.fillna(False)] = np.sign(
                strength_z[condition.fillna(False)]
            ).astype(int)
    else:
        raise ImplementationConformanceError(f"unsupported pair candidate: {variant}")
    return direction


def _synthetic_pair_frame(metrics: pd.DataFrame, beta: float) -> pd.DataFrame:
    safe_beta = max(0.0, float(beta))
    close_raw = metrics["closeAlt"] / np.power(metrics["closeBtc"], safe_beta)
    open_raw = metrics["openAlt"] / np.power(metrics["openBtc"], safe_beta)
    high_raw = metrics["highAlt"] / np.power(metrics["lowBtc"], safe_beta)
    low_raw = metrics["lowAlt"] / np.power(metrics["highBtc"], safe_beta)
    scale = 100.0 / float(close_raw.dropna().iloc[0])
    return pd.DataFrame(
        {
            "date": metrics["date"],
            "open": open_raw * scale,
            "high": high_raw * scale,
            "low": low_raw * scale,
            "close": close_raw * scale,
            "volume": metrics[["volumeAlt", "volumeBtc"]].min(axis=1),
            "residualZ": metrics["residualZ"],
            "pairCorrelation": metrics["pairCorrelation"],
        }
    )


def replay_pair_candidate(
    candidate: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame],
    *,
    round_trip_cost_rate: float,
) -> list[dict[str, Any]]:
    ordered = {symbol: _ordered(frame) for symbol, frame in frames.items()}
    btc = ordered.get("BTC-USDT-SWAP")
    if btc is None:
        raise ImplementationConformanceError("pair replay requires BTC-USDT-SWAP")
    events: list[dict[str, Any]] = []
    for symbol, alt in sorted(ordered.items()):
        if symbol == "BTC-USDT-SWAP":
            continue
        metrics = _pair_metrics(candidate, _aligned_pair(alt, btc))
        signals = _signals(candidate, metrics)
        next_available = 0
        for signal_index in np.flatnonzero(signals.to_numpy()):
            signal_index = int(signal_index)
            if signal_index < next_available or signal_index >= len(metrics) - 1:
                continue
            beta = float(metrics.iloc[signal_index]["beta"])
            if not np.isfinite(beta) or beta <= 0:
                continue
            synthetic = _synthetic_pair_frame(metrics, beta)
            side = int(signals.iloc[signal_index])
            stop = dict(candidate["initialStopDefinition"])
            if stop["kind"] == "residual_z":
                z = abs(float(metrics.iloc[signal_index]["residualZ"]))
                z_distance = float(stop["maximumAdverseZ"]) - z
                residual_std = float(metrics.iloc[signal_index]["residualStd"])
                risk_distance = z_distance * residual_std * float(synthetic.iloc[signal_index]["close"])
            else:
                risk_distance = float(_atr(synthetic).iloc[signal_index]) * float(stop["multiple"])
            if not np.isfinite(risk_distance) or risk_distance <= 0:
                continue
            policy = exit_policy_from_dict(dict(candidate["exitPolicy"]))
            structure_mask = None
            if policy.mode.value in {"structure_or_time", "hybrid"}:
                structure_mask = compile_structure_rule(candidate, synthetic, side=side)
            result = replay_exit_policy(
                frame=synthetic,
                signalPosition=signal_index,
                direction="long" if side > 0 else "short",
                riskDistance=risk_distance,
                policy=policy,
                costs=_costs(round_trip_cost_rate),
                atrValues=_atr(synthetic),
                structureExitMask=structure_mask,
                fundingRate=None,
            )
            if result.exitPolicyHash != str(candidate["exitPolicyHash"]):
                raise ImplementationConformanceError("pair exit-policy hash mismatch")
            payload = exit_execution_to_dict(result)
            alt_direction = "long" if side > 0 else "short"
            btc_direction = "short" if side > 0 else "long"
            payload.update(
                {
                    "candidateId": candidate["candidateId"],
                    "familyId": candidate["familyId"],
                    "variantId": candidate["variantId"],
                    "symbol": f"{symbol}|BTC-USDT-SWAP",
                    "marketLegCount": 2,
                    "marketLegs": [
                        {"symbol": symbol, "direction": alt_direction, "hedgeWeight": 1.0},
                        {"symbol": "BTC-USDT-SWAP", "direction": btc_direction, "hedgeWeight": beta},
                    ],
                    "twoLegCostMultiplier": 2.0,
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
    return sorted(events, key=lambda row: (row["entryTimestamp"], row["symbol"]))
