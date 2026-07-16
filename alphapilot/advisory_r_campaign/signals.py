"""Causal signal replay for the frozen V13.27.1.15 candidate inventory."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from alphapilot.exit_policy import (
    ExitCosts,
    ExitPolicyMode,
    exit_execution_to_dict,
    exit_policy_from_dict,
    replay_exit_policy,
)

from .conformance import ImplementationConformanceError


def _ordered(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], utc=True)
    if "confirmed" in result.columns:
        result = result[pd.to_numeric(result["confirmed"], errors="coerce") == 1]
    for column in ("open", "high", "low", "close", "volume"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return (
        result.dropna(subset=["date", "open", "high", "low", "close"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


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


def _rolling_z(values: pd.Series, window: int) -> pd.Series:
    mean = values.rolling(window, min_periods=window).mean()
    standard = values.rolling(window, min_periods=window).std(ddof=0).replace(0, np.nan)
    return (values - mean) / standard


def _market_close(frames: Mapping[str, pd.DataFrame]) -> pd.Series:
    panel = pd.concat(
        {
            symbol: frame.set_index("date")["close"]
            for symbol, frame in frames.items()
            if not frame.empty
        },
        axis=1,
    ).sort_index()
    return panel.median(axis=1, skipna=True)


def _aligned(values: pd.Series, dates: pd.Series) -> pd.Series:
    return values.reindex(pd.DatetimeIndex(dates)).ffill().reset_index(drop=True)


def _signal_series(
    candidate: Mapping[str, Any],
    frame: pd.DataFrame,
    *,
    btc_close: pd.Series,
    market_close: pd.Series,
) -> pd.Series:
    variant = str(candidate["variantId"])
    feature = dict(candidate["featureDefinition"])
    entry = dict(candidate["entryDefinition"])
    close = frame["close"]
    returns = close.pct_change()
    btc = _aligned(btc_close, frame["date"])
    btc_returns = btc.pct_change()
    market_returns = _aligned(market_close, frame["date"]).pct_change()
    residual = returns - market_returns
    direction = pd.Series(0, index=frame.index, dtype="int64")

    if variant == "S01":
        window = int(feature["residualWindow"])
        residual_z = _rolling_z(residual, window)
        recovery = residual_z.diff()
        btc_bear = btc < btc.ewm(span=200, adjust=False, min_periods=200).mean()
        condition = (
            (residual_z.shift(1) <= float(feature["residualZMaximum"]))
            & (recovery >= float(entry["minimumRecoveryZ"]))
            & btc_bear
        )
        direction.loc[condition.fillna(False)] = 1
    elif variant in {"S02", "S03"}:
        impulse = _rolling_z(btc_returns, 168)
        threshold = float(feature["btcImpulseZ"])
        follower_fraction = returns.abs() / btc_returns.abs().replace(0, np.nan)
        if variant == "S02":
            condition = (impulse.abs() >= threshold) & (
                follower_fraction <= float(entry["maximumFollowerMoveFraction"])
            )
            direction.loc[condition.fillna(False)] = np.sign(impulse[condition.fillna(False)]).astype(int)
        else:
            overreaction = follower_fraction >= float(feature["overreactionRatio"])
            turn = np.sign(returns) != np.sign(returns.shift(1))
            condition = (impulse.abs() >= threshold) & overreaction & turn
            direction.loc[condition.fillna(False)] = -np.sign(returns[condition.fillna(False)]).astype(int)
    elif variant == "S04":
        window = int(feature["pairWindow"])
        residual_pair = returns - btc_returns
        residual_z = _rolling_z(residual_pair, window)
        correlation = returns.rolling(window, min_periods=window).corr(btc_returns)
        extreme = residual_z.abs() >= float(feature["entryResidualZ"])
        turn = residual_z.abs() < residual_z.abs().shift(1)
        condition = extreme & turn & (correlation >= float(feature["minimumCorrelation"]))
        direction.loc[condition.fillna(False)] = -np.sign(residual_z[condition.fillna(False)]).astype(int)
    elif variant in {"S05", "S06"}:
        window = int(feature["correlationWindow"])
        correlation = returns.rolling(window, min_periods=window).corr(btc_returns)
        baseline = correlation.shift(6).rolling(window, min_periods=max(12, window // 2)).mean()
        residual_pair = returns - btc_returns
        break_condition = (baseline >= 0.65) & (correlation <= float(feature["breakMaximum"]))
        if variant == "S05":
            turn = residual_pair.abs() < residual_pair.abs().shift(1)
            condition = break_condition & turn
            direction.loc[condition.fillna(False)] = -np.sign(residual_pair[condition.fillna(False)]).astype(int)
        else:
            strength = residual_pair.rolling(int(feature["relativeStrengthBars"]), min_periods=2).sum()
            strength_z = _rolling_z(strength, window)
            condition = break_condition & (strength_z.abs() >= float(entry["minimumRelativeMoveZ"]))
            direction.loc[condition.fillna(False)] = np.sign(strength_z[condition.fillna(False)]).astype(int)
    elif variant == "S07":
        atr_fraction = _atr(frame) / close.replace(0, np.nan)
        window = int(feature["atrPercentileWindow"])
        rank = atr_fraction.rolling(window, min_periods=window).rank(pct=True)
        location = (close - frame["low"]) / (frame["high"] - frame["low"]).replace(0, np.nan)
        shock = rank >= float(feature["shockPercentile"])
        upper = location >= float(feature["closeLocationThreshold"])
        lower = location <= 1.0 - float(feature["closeLocationThreshold"])
        direction.loc[(shock & upper).fillna(False)] = 1
        direction.loc[(shock & lower).fillna(False)] = -1
    elif variant == "S08":
        window = int(feature["trendWindow"])
        trend = close.pct_change(window)
        volume_ratio = frame["volume"] / frame["volume"].rolling(24, min_periods=12).mean()
        hour = frame["date"].dt.hour
        condition = hour.isin([int(value) for value in feature["utcEntryHours"]]) & (
            volume_ratio >= float(feature["minimumVolumeRatio"])
        )
        direction.loc[condition.fillna(False)] = np.sign(trend[condition.fillna(False)]).replace(0, 1).astype(int)
    elif variant == "S09":
        window = int(feature["betaWindow"])
        covariance = returns.rolling(window, min_periods=window).cov(btc_returns)
        variance = btc_returns.rolling(window, min_periods=window).var().replace(0, np.nan)
        beta = covariance / variance
        btc_weak = btc.pct_change(int(feature["btcTrendWindow"])) < 0
        condition = btc_weak & (beta <= beta.rolling(window, min_periods=window).quantile(0.3))
        direction.loc[condition.fillna(False)] = 1
    elif variant == "S10":
        residual_turn = (residual > residual.shift(1)).astype(int) - (residual < residual.shift(1)).astype(int)
        volume_ratio = frame["volume"] / frame["volume"].rolling(42, min_periods=20).mean()
        volume_vote = np.sign(returns).where(volume_ratio >= 1.25, 0).astype(int)
        trend = close.ewm(span=12, adjust=False).mean() - close.ewm(span=48, adjust=False).mean()
        trend_vote = np.sign(trend).astype(int)
        vote = residual_turn + volume_vote + trend_vote
        minimum_votes = int(feature["minimumVotes"])
        direction.loc[vote >= minimum_votes] = 1
        direction.loc[vote <= -minimum_votes] = -1

    return direction.fillna(0).astype(int)


def _structure_exit_mask(
    candidate: Mapping[str, Any],
    frame: pd.DataFrame,
    *,
    side: int,
    btc_close: pd.Series,
    market_close: pd.Series,
) -> pd.Series:
    policy = exit_policy_from_dict(dict(candidate["exitPolicy"]))
    rule = dict(policy.parameters.get("structureRule") or {})
    kind = str(rule.get("kind") or "")
    close = frame["close"]
    open_ = frame["open"]
    if kind == "trend_invalidation":
        fast_window = int(rule["fastWindow"])
        slow_window = int(rule["slowWindow"])
        fast = close.rolling(fast_window, min_periods=fast_window).mean()
        slow = close.rolling(slow_window, min_periods=slow_window).mean()
        result = fast <= slow if side > 0 else fast >= slow
    elif kind == "event_reversal":
        confirmation = int(rule["confirmationBars"])
        opposite = close < open_ if side > 0 else close > open_
        result = opposite.rolling(confirmation, min_periods=confirmation).sum() == confirmation
    elif kind == "residual_neutral_zone":
        variant = str(candidate["variantId"])
        if variant == "S01":
            benchmark_returns = _aligned(market_close, frame["date"]).pct_change()
            window = int(candidate["featureDefinition"]["residualWindow"])
        else:
            benchmark_returns = _aligned(btc_close, frame["date"]).pct_change()
            window = int(candidate["featureDefinition"]["pairWindow"])
        residual_z = _rolling_z(close.pct_change() - benchmark_returns, window)
        result = residual_z.abs() <= float(rule["absoluteZscoreMaximum"])
    elif kind == "correlation_recovery":
        btc_returns = _aligned(btc_close, frame["date"]).pct_change()
        window = int(candidate["featureDefinition"]["correlationWindow"])
        result = close.pct_change().rolling(window, min_periods=window).corr(btc_returns) >= float(
            rule["minimumCorrelation"]
        )
    elif kind == "beta_rank_exit":
        if "betaRankPercentile" not in frame:
            raise ValueError("beta_rank_exit requires cross-sectional betaRankPercentile")
        result = pd.to_numeric(frame["betaRankPercentile"], errors="coerce") <= float(
            rule["maximumRankPercentile"]
        )
    else:
        raise ValueError(f"unsupported structure rule: {kind}")
    return pd.Series(result, index=frame.index).fillna(False).astype(bool)


def _formal_costs(round_trip_cost_rate: float) -> ExitCosts:
    total_bps = round_trip_cost_rate * 10_000
    return ExitCosts(
        feeBpsPerSide=total_bps * 0.25,
        slippageBpsPerSide=total_bps * 0.125,
        spreadBpsPerSide=total_bps * 0.125,
    )


def _replay_event(
    candidate: Mapping[str, Any],
    frame: pd.DataFrame,
    atr: pd.Series,
    *,
    signal_index: int,
    side: int,
    symbol: str,
    round_trip_cost_rate: float,
    btc_close: pd.Series,
    market_close: pd.Series,
) -> dict[str, Any] | None:
    if signal_index >= len(frame) - 1 or pd.isna(atr.iloc[signal_index]):
        return None
    stop_definition = dict(candidate["initialStopDefinition"])
    if stop_definition.get("kind") != "atr":
        raise ValueError(
            f"{candidate['variantId']} requires a dedicated pair/portfolio replay adapter"
        )
    risk_distance = float(atr.iloc[signal_index]) * float(stop_definition["multiple"])
    if not np.isfinite(risk_distance) or risk_distance <= 0:
        return None
    policy = exit_policy_from_dict(dict(candidate["exitPolicy"]))
    structure_mask = None
    structure_mode = policy.mode is ExitPolicyMode.STRUCTURE_OR_TIME or (
        policy.mode is ExitPolicyMode.HYBRID
        and policy.parameters.get("remainderMode") == "structure"
    )
    if structure_mode:
        structure_mask = _structure_exit_mask(
            candidate,
            frame,
            side=side,
            btc_close=btc_close,
            market_close=market_close,
        )
    result = replay_exit_policy(
        frame=frame,
        signalPosition=signal_index,
        direction="long" if side > 0 else "short",
        riskDistance=risk_distance,
        policy=policy,
        costs=_formal_costs(round_trip_cost_rate),
        atrValues=atr,
        structureExitMask=structure_mask,
        fundingRate=None,
    )
    if result.exitPolicyHash != str(candidate["exitPolicyHash"]):
        raise ImplementationConformanceError(
            f"exit-policy hash mismatch for {candidate['candidateId']}"
        )
    event = exit_execution_to_dict(result)
    event.update(
        {
            "candidateId": candidate["candidateId"],
            "familyId": candidate["familyId"],
            "variantId": candidate["variantId"],
            "symbol": symbol,
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
            "initialStopMayWiden": policy.initialStopMayWiden,
            "fundingR": None,
        }
    )
    return event


def replay_candidate(
    candidate: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame],
    *,
    round_trip_cost_rate: float,
) -> list[dict[str, Any]]:
    """Replay a frozen candidate without reading future bars at signal time."""

    ordered_frames = {symbol: _ordered(frame) for symbol, frame in frames.items()}
    if not ordered_frames:
        return []
    btc_frame = ordered_frames.get("BTC-USDT-SWAP")
    if btc_frame is None:
        btc_frame = next(iter(ordered_frames.values()))
    btc_close = btc_frame.set_index("date")["close"]
    market_close = _market_close(ordered_frames)
    events: list[dict[str, Any]] = []
    for symbol, frame in sorted(ordered_frames.items()):
        if len(frame) < 60:
            continue
        signal = _signal_series(
            candidate,
            frame,
            btc_close=btc_close,
            market_close=market_close,
        )
        atr = _atr(frame)
        next_available = 0
        for signal_index in np.flatnonzero(signal.to_numpy()):
            if signal_index < next_available or signal_index >= len(frame) - 1:
                continue
            event = _replay_event(
                candidate,
                frame,
                atr,
                signal_index=int(signal_index),
                side=int(signal.iloc[signal_index]),
                symbol=symbol,
                round_trip_cost_rate=round_trip_cost_rate,
                btc_close=btc_close,
                market_close=market_close,
            )
            if event is None:
                continue
            events.append(event)
            next_available = int(event["exitIndex"]) + 1
    return sorted(events, key=lambda row: (row["entryTimestamp"], row["symbol"]))
