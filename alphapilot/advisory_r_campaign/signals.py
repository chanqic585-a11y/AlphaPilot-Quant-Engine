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
from .structure_rules import compile_structure_rule


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


def _lagged_impulse_context(
    *,
    impulse_z: pd.Series,
    btc_returns: pd.Series,
    follower_close: pd.Series,
    lag_window: int,
) -> pd.DataFrame:
    """Select the strongest prior BTC impulse and expose its causal follower path."""

    rows: list[dict[str, float]] = []
    for position in range(len(impulse_z)):
        best_lag = 0
        best_z = 0.0
        for lag in range(1, lag_window + 1):
            source = position - lag
            if source < 0:
                continue
            value = float(impulse_z.iloc[source])
            if np.isfinite(value) and abs(value) > abs(best_z):
                best_z = value
                best_lag = lag
        if best_lag == 0:
            rows.append(
                {
                    "impulseZ": np.nan,
                    "impulseReturn": np.nan,
                    "lag": 0,
                    "followerMoveFraction": np.nan,
                    "maximumFollowerMoveFraction": np.nan,
                }
            )
            continue
        source = position - best_lag
        impulse_return = float(btc_returns.iloc[source])
        base = float(follower_close.iloc[source])
        follower_path = follower_close.iloc[source + 1 : position + 1]
        path_moves = (follower_path / base - 1.0).abs()
        current_move = abs(float(follower_close.iloc[position]) / base - 1.0)
        denominator = abs(impulse_return)
        rows.append(
            {
                "impulseZ": best_z,
                "impulseReturn": impulse_return,
                "lag": best_lag,
                "followerMoveFraction": current_move / denominator if denominator else np.nan,
                "maximumFollowerMoveFraction": float(path_moves.max()) / denominator
                if denominator and not path_moves.empty
                else np.nan,
            }
        )
    return pd.DataFrame(rows, index=impulse_z.index)


def _cross_sectional_beta_ranks(
    frames: Mapping[str, pd.DataFrame],
    *,
    btc_close: pd.Series,
    window: int,
) -> dict[str, pd.Series]:
    beta_columns: dict[str, pd.Series] = {}
    btc_returns = btc_close.pct_change()
    btc_variance = btc_returns.rolling(window, min_periods=window).var().replace(0, np.nan)
    for symbol, frame in frames.items():
        close = frame.set_index("date")["close"]
        returns = close.pct_change().reindex(btc_close.index)
        beta_columns[symbol] = returns.rolling(window, min_periods=window).cov(btc_returns) / btc_variance
    ranks = pd.DataFrame(beta_columns).rank(axis=1, pct=True, method="average")
    return {
        symbol: _aligned(ranks[symbol], frame["date"])
        for symbol, frame in frames.items()
        if symbol in ranks
    }


def weak_signal_components(
    candidate: Mapping[str, Any],
    frame: pd.DataFrame,
    *,
    market_close: pd.Series,
) -> pd.DataFrame:
    """Compile only the three frozen S10 weak signals for correlation evidence."""

    configured = list(dict(candidate["featureDefinition"])["signals"])
    allowed = {"residual_turn", "volume_surprise", "trend_slope"}
    if set(configured) != allowed:
        raise ImplementationConformanceError("S10 weak-signal set differs from frozen definition")
    close = frame["close"]
    returns = close.pct_change()
    market_returns = _aligned(market_close, frame["date"]).pct_change()
    residual = returns - market_returns
    residual_turn = np.sign(residual.diff()).fillna(0).astype(int)
    volume_ratio = frame["volume"] / frame["volume"].rolling(42, min_periods=20).mean()
    volume_surprise = np.sign(returns).where(volume_ratio >= 1.25, 0).fillna(0).astype(int)
    trend = close.rolling(12, min_periods=12).mean() - close.rolling(48, min_periods=48).mean()
    trend_slope = np.sign(trend).fillna(0).astype(int)
    return pd.DataFrame(
        {
            "residual_turn": residual_turn,
            "volume_surprise": volume_surprise,
            "trend_slope": trend_slope,
        },
        index=frame.index,
    )[configured]


def weak_signal_correlation_audit(components: pd.DataFrame) -> dict[str, Any]:
    """Return the observed Development correlation matrix without claiming orthogonality."""

    expected = ["residual_turn", "volume_surprise", "trend_slope"]
    if list(components.columns) != expected:
        raise ImplementationConformanceError(
            "S10 correlation audit requires the three frozen weak signals in order"
        )
    numeric = components.apply(pd.to_numeric, errors="coerce")
    matrix = numeric.corr().fillna(0.0)
    for name in expected:
        if numeric[name].notna().any():
            matrix.loc[name, name] = 1.0
    return {
        "schemaVersion": "advisory_r_weak_signal_correlation_v1",
        "componentNames": expected,
        "rowCount": int(len(numeric)),
        "correlationMatrix": {
            row: {column: float(matrix.loc[row, column]) for column in expected}
            for row in expected
        },
        "orthogonalityClaimed": False,
    }


def _signal_series(
    candidate: Mapping[str, Any],
    frame: pd.DataFrame,
    *,
    btc_close: pd.Series,
    market_close: pd.Series,
    beta_rank: pd.Series | None = None,
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
        recovery_bars = int(feature["recoveryBars"])
        residual_z = _rolling_z(residual, window)
        recovery_steps = residual_z.diff() > 0
        complete_recovery = (
            recovery_steps.rolling(recovery_bars, min_periods=recovery_bars).sum()
            == recovery_bars
        )
        recovery_size = residual_z - residual_z.shift(recovery_bars)
        if str(feature["marketRegime"]) != "btc_close_below_ema_200":
            raise ImplementationConformanceError("unsupported S01 market regime")
        btc_bear = btc < btc.ewm(span=200, adjust=False, min_periods=200).mean()
        condition = (
            (residual_z.shift(recovery_bars) <= float(feature["residualZMaximum"]))
            & complete_recovery
            & (recovery_size >= float(entry["minimumRecoveryZ"]))
            & btc_bear
        )
        direction.loc[condition.fillna(False)] = 1
    elif variant in {"S02", "S03"}:
        beta_window = int(feature.get("betaWindow") or 168)
        impulse = _rolling_z(btc_returns, beta_window)
        context = _lagged_impulse_context(
            impulse_z=impulse,
            btc_returns=btc_returns,
            follower_close=close,
            lag_window=int(feature["lagWindow"]),
        )
        qualifying_impulse = context["impulseZ"].abs() >= float(feature["btcImpulseZ"])
        if variant == "S02":
            if beta_rank is None:
                raise ImplementationConformanceError("S02 requires cross-sectional beta rank")
            high_beta = pd.Series(beta_rank, index=frame.index) >= 0.5
            underreaction = context["followerMoveFraction"] <= float(
                entry["maximumFollowerMoveFraction"]
            )
            condition = qualifying_impulse & high_beta & underreaction
            direction.loc[condition.fillna(False)] = np.sign(
                context.loc[condition.fillna(False), "impulseZ"]
            ).astype(int)
        else:
            confirmation_bars = int(entry["confirmationBars"])
            impulse_sign = np.sign(context["impulseZ"])
            opposite = returns * impulse_sign < 0
            confirmed = (
                opposite.rolling(confirmation_bars, min_periods=confirmation_bars).sum()
                == confirmation_bars
            )
            overreaction = context["maximumFollowerMoveFraction"] >= float(
                feature["overreactionRatio"]
            )
            condition = qualifying_impulse & overreaction & confirmed
            direction.loc[condition.fillna(False)] = -np.sign(
                context.loc[condition.fillna(False), "impulseZ"]
            ).astype(int)
    elif variant in {"S04", "S05", "S06", "S09"}:
        raise ImplementationConformanceError(
            f"{variant} must use its pair or portfolio replay adapter"
        )
    elif variant == "S07":
        atr_fraction = _atr(frame) / close.replace(0, np.nan)
        window = int(feature["atrPercentileWindow"])
        rank = atr_fraction.rolling(window, min_periods=window).rank(pct=True)
        location = (close - frame["low"]) / (frame["high"] - frame["low"]).replace(0, np.nan)
        shock = rank >= float(feature["shockPercentile"])
        upper = location >= float(feature["closeLocationThreshold"])
        lower = location <= 1.0 - float(feature["closeLocationThreshold"])
        confirmation_bars = int(entry["confirmationBars"])
        if confirmation_bars != 1:
            raise ImplementationConformanceError("S07 only supports one-bar confirmation")
        direction.loc[((shock & upper).shift(1).fillna(False) & (returns > 0))] = 1
        direction.loc[((shock & lower).shift(1).fillna(False) & (returns < 0))] = -1
    elif variant == "S08":
        trend_window = int(feature["trendWindow"])
        prior_bars = int(entry["directionFromPriorBars"])
        prior_direction = close.pct_change(prior_bars).shift(1)
        broad_trend = close.pct_change(trend_window).shift(1)
        volume_ratio = frame["volume"] / frame["volume"].rolling(24, min_periods=3).mean()
        hour = frame["date"].dt.hour
        condition = hour.isin([int(value) for value in feature["utcEntryHours"]]) & (
            volume_ratio >= float(feature["minimumVolumeRatio"])
        ) & (np.sign(prior_direction) == np.sign(broad_trend))
        direction.loc[condition.fillna(False)] = np.sign(
            prior_direction[condition.fillna(False)]
        ).replace(0, 1).astype(int)
    elif variant == "S10":
        components = weak_signal_components(candidate, frame, market_close=market_close)
        vote = components.sum(axis=1)
        minimum_votes = int(feature["minimumVotes"])
        confirmation_bars = int(entry["confirmationBars"])
        positive = vote >= minimum_votes
        negative = vote <= -minimum_votes
        positive_confirmed = (
            positive.rolling(confirmation_bars, min_periods=confirmation_bars).sum()
            == confirmation_bars
        )
        negative_confirmed = (
            negative.rolling(confirmation_bars, min_periods=confirmation_bars).sum()
            == confirmation_bars
        )
        direction.loc[positive_confirmed] = 1
        direction.loc[negative_confirmed] = -1
    else:
        raise ImplementationConformanceError(f"unsupported frozen variant: {variant}")

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
    working = frame.copy()
    if kind == "residual_neutral_zone" and "residualZ" not in working:
        if str(candidate["variantId"]) != "S01":
            raise ValueError("pair residual exits require the pair replay adapter")
        benchmark_returns = _aligned(market_close, frame["date"]).pct_change()
        window = int(candidate["featureDefinition"]["residualWindow"])
        working["residualZ"] = _rolling_z(
            working["close"].pct_change() - benchmark_returns,
            window,
        )
    return compile_structure_rule(candidate, working, side=side)


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
    variant = str(candidate["variantId"])
    if variant in {"S04", "S05", "S06"}:
        from .pair_replay import replay_pair_candidate

        return replay_pair_candidate(
            candidate,
            ordered_frames,
            round_trip_cost_rate=round_trip_cost_rate,
        )
    if variant == "S09":
        from .portfolio_replay import replay_portfolio_candidate

        return replay_portfolio_candidate(
            candidate,
            ordered_frames,
            round_trip_cost_rate=round_trip_cost_rate,
        )
    btc_frame = ordered_frames.get("BTC-USDT-SWAP")
    if btc_frame is None:
        btc_frame = next(iter(ordered_frames.values()))
    btc_close = btc_frame.set_index("date")["close"]
    market_close = _market_close(ordered_frames)
    beta_ranks = (
        _cross_sectional_beta_ranks(
            ordered_frames,
            btc_close=btc_close,
            window=int(candidate["featureDefinition"]["betaWindow"]),
        )
        if variant == "S02"
        else {}
    )
    events: list[dict[str, Any]] = []
    for symbol, frame in sorted(ordered_frames.items()):
        if len(frame) < 60:
            continue
        signal = _signal_series(
            candidate,
            frame,
            btc_close=btc_close,
            market_close=market_close,
            beta_rank=beta_ranks.get(symbol),
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
