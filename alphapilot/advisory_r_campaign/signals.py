"""Causal signal replay for the frozen V13.27.1.15 candidate inventory."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd


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


def _structure_invalidated(
    candidate: Mapping[str, Any], frame: pd.DataFrame, index: int, side: int
) -> bool:
    if index < 48:
        return False
    fast = float(frame["close"].iloc[index - 11 : index + 1].mean())
    slow = float(frame["close"].iloc[index - 47 : index + 1].mean())
    return fast <= slow if side > 0 else fast >= slow


def _simulate_event(
    candidate: Mapping[str, Any],
    frame: pd.DataFrame,
    atr: pd.Series,
    *,
    signal_index: int,
    side: int,
    symbol: str,
    round_trip_cost_rate: float,
) -> dict[str, Any] | None:
    entry_index = signal_index + 1
    if entry_index >= len(frame) or pd.isna(atr.iloc[signal_index]):
        return None
    entry_price = float(frame.iloc[entry_index]["open"])
    atr_value = float(atr.iloc[signal_index])
    stop_definition = dict(candidate["initialStopDefinition"])
    stop_multiple = float(stop_definition.get("multiple") or 1.5)
    risk = atr_value * stop_multiple
    if not np.isfinite(risk) or risk <= 0:
        return None
    stop_price = entry_price - side * risk
    initial_stop_price = stop_price
    policy = dict(candidate["exitPolicy"])
    parameters = dict(policy.get("parameters") or {})
    mode = str(policy["mode"])
    maximum_hold = int(policy.get("maximumHoldBars") or candidate["maximumHold"])
    target_r = float(parameters.get("targetR") or parameters.get("partialAtR") or 0.0)
    partial_fraction = float(parameters.get("partialFraction") or 0.0)
    trailing_multiple = float(parameters.get("trailingAtrMultiple") or 0.0)
    remaining = 1.0
    gross_r = 0.0
    partial_taken = False
    exit_reason = "time"
    exit_index = min(len(frame) - 1, entry_index + maximum_hold)
    exit_price = float(frame.iloc[exit_index]["close"])
    highest = entry_price
    lowest = entry_price
    mfe_r = 0.0
    mae_r = 0.0

    for index in range(entry_index, exit_index + 1):
        row = frame.iloc[index]
        favorable = ((float(row["high"]) - entry_price) * side) / risk
        adverse = ((float(row["low"]) - entry_price) * side) / risk
        if side < 0:
            favorable = ((entry_price - float(row["low"])) / risk)
            adverse = ((entry_price - float(row["high"])) / risk)
        mfe_r = max(mfe_r, favorable)
        mae_r = min(mae_r, adverse)
        highest = max(highest, float(row["high"]))
        lowest = min(lowest, float(row["low"]))

        stop_hit = float(row["low"]) <= stop_price if side > 0 else float(row["high"]) >= stop_price
        if stop_hit:
            gross_r += remaining * -1.0
            exit_reason = "trailing" if partial_taken and stop_price != initial_stop_price else "stop"
            exit_index = index
            exit_price = stop_price
            break

        if mode == "fixed_r" and target_r > 0:
            target_price = entry_price + side * target_r * risk
            target_hit = float(row["high"]) >= target_price if side > 0 else float(row["low"]) <= target_price
            if target_hit:
                gross_r += remaining * target_r
                exit_reason = "target"
                exit_index = index
                exit_price = target_price
                remaining = 0.0
                break

        if mode in {"partial_then_trailing", "hybrid"} and not partial_taken:
            partial_at_r = float(parameters.get("partialAtR") or 0.0)
            partial_price = entry_price + side * partial_at_r * risk
            partial_hit = float(row["high"]) >= partial_price if side > 0 else float(row["low"]) <= partial_price
            if partial_hit:
                gross_r += partial_fraction * partial_at_r
                remaining -= partial_fraction
                partial_taken = True

        if partial_taken and trailing_multiple > 0 and not pd.isna(atr.iloc[index]):
            trail_distance = trailing_multiple * float(atr.iloc[index])
            if side > 0:
                stop_price = max(stop_price, highest - trail_distance)
            else:
                stop_price = min(stop_price, lowest + trail_distance)

        if mode in {"structure_or_time", "hybrid"} and _structure_invalidated(
            candidate, frame, index, side
        ):
            exit_price = float(row["close"])
            gross_r += remaining * ((exit_price - entry_price) * side / risk)
            exit_reason = "structure"
            exit_index = index
            remaining = 0.0
            break
    if remaining > 0 and exit_reason == "time":
        gross_r += remaining * ((exit_price - entry_price) * side / risk)
    cost_r = round_trip_cost_rate * entry_price / risk
    net_r = gross_r - cost_r
    giveback = max(0.0, mfe_r - gross_r)
    return {
        "candidateId": candidate["candidateId"],
        "familyId": candidate["familyId"],
        "variantId": candidate["variantId"],
        "symbol": symbol,
        "signalIndex": signal_index,
        "entryIndex": entry_index,
        "exitIndex": exit_index,
        "entryTimestamp": pd.Timestamp(frame.iloc[entry_index]["date"]).isoformat(),
        "exitTimestamp": pd.Timestamp(frame.iloc[exit_index]["date"]).isoformat(),
        "side": "long" if side > 0 else "short",
        "entryPrice": entry_price,
        "exitPrice": exit_price,
        "initialStopPrice": initial_stop_price,
        "initialStopMayWiden": False,
        "targetR": float(parameters["targetR"]) if "targetR" in parameters else None,
        "grossR": gross_r,
        "feesR": cost_r * 0.5,
        "spreadProxyR": cost_r * 0.25,
        "slippageR": cost_r * 0.25,
        "fundingR": None,
        "costR": cost_r,
        "netR": net_r,
        "realizedGrossR": gross_r,
        "realizedNetR": net_r,
        "exitReason": exit_reason,
        "partialExit": partial_taken,
        "mfeR": mfe_r,
        "maeR": mae_r,
        "profitGivebackR": giveback,
        "exitPolicyMode": mode,
        "exitPolicyHash": candidate["exitPolicyHash"],
        "maximumHold": maximum_hold,
    }


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
            event = _simulate_event(
                candidate,
                frame,
                atr,
                signal_index=int(signal_index),
                side=int(signal.iloc[signal_index]),
                symbol=symbol,
                round_trip_cost_rate=round_trip_cost_rate,
            )
            if event is None:
                continue
            events.append(event)
            next_available = int(event["exitIndex"]) + 1
    return sorted(events, key=lambda row: (row["entryTimestamp"], row["symbol"]))
