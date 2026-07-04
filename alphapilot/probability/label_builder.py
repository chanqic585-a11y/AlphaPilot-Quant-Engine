"""Build point-in-time probability candidate samples and forward labels.

Feature columns are calculated from the current candle and prior candles only.
Forward candles are used exclusively for labels. This module does not run a
strategy backtest, enter Dry-run, call exchange APIs, read accounts, create
orders, or auto trade.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.probability.condition_buckets import (
    bollinger_position_bucket,
    btc_state,
    ema_distance_bucket,
    liquidity_bucket,
    regime_candidate,
    round_optional,
    rsi_bucket,
    safe_float,
    volatility_bucket,
)
from alphapilot.probability.probability_schema import (
    ProbabilityCandidateSample,
    ProbabilityDatasetConfig,
    ProbabilityLabel,
)
from alphapilot.universe.dynamic_universe_schema import DynamicUniverseConfig
from alphapilot.universe.historical_dynamic_universe_builder import load_pair_data, parse_timerange


@dataclass
class ProbabilityDatasetBuild:
    samples: list[ProbabilityCandidateSample]
    snapshotCount: int
    insufficientDataCount: int
    warnings: list[str]
    pairLoadErrors: dict[str, str]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def read_universe_snapshots(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing universe snapshots: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Universe snapshots must be a list: {path}")
    return payload


def _snapshot_in_timerange(snapshot_date: str, timerange: str) -> bool:
    start, end = parse_timerange(timerange)
    parsed = datetime.strptime(snapshot_date, "%Y-%m-%d").replace(tzinfo=UTC)
    if start and parsed < start:
        return False
    if end and parsed > end:
        return False
    return True


def _pair_score_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    scores = snapshot.get("pairScores", [])
    if not isinstance(scores, list):
        return {}
    return {str(score.get("pair")): score for score in scores if isinstance(score, dict) and score.get("pair")}


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy().sort_values("date").reset_index(drop=True)
    result["quoteVolume"] = result["close"] * result["volume"]

    result["ema20"] = result["close"].ewm(span=20, adjust=False).mean()
    result["ema50"] = result["close"].ewm(span=50, adjust=False).mean()
    result["ema200"] = result["close"].ewm(span=200, adjust=False).mean()

    delta = result["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    result["rsi14"] = 100 - (100 / (1 + rs))

    ema12 = result["close"].ewm(span=12, adjust=False).mean()
    ema26 = result["close"].ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    result["macdHist"] = macd - signal

    rolling_close = result["close"].rolling(window=20, min_periods=20)
    result["bbMiddle"] = rolling_close.mean()
    bb_std = rolling_close.std(ddof=0)
    result["bbUpper"] = result["bbMiddle"] + (bb_std * 2)
    result["bbLower"] = result["bbMiddle"] - (bb_std * 2)

    previous_close = result["close"].shift(1)
    true_range = pd.concat(
        [
            result["high"] - result["low"],
            (result["high"] - previous_close).abs(),
            (result["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr14 = true_range.rolling(window=14, min_periods=14).mean()
    result["atrPct"] = atr14 / result["close"]

    avg_volume = result["volume"].rolling(window=20, min_periods=20).mean()
    result["volumeRatio"] = result["volume"] / avg_volume.replace(0, pd.NA)
    return result


def _load_frames(config: ProbabilityDatasetConfig, pairs: set[str]) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    frames: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
    universe_config = DynamicUniverseConfig(
        timeframeForRanking=config.timeframe,
        timerange=config.timerange,
        dataPath=config.dataPath,
    )
    for pair in sorted(pairs):
        frame, error = load_pair_data(pair, universe_config)
        if frame is None:
            errors[pair] = error or "unknown_load_error"
            continue
        frames[pair] = add_indicators(frame)
    return frames, errors


def _row_at_or_after(frame: pd.DataFrame, timestamp: pd.Timestamp) -> tuple[int | None, pd.Series | None]:
    matches = frame.index[frame["date"] >= timestamp].tolist()
    if not matches:
        return None, None
    idx = int(matches[0])
    return idx, frame.iloc[idx]


def _future_label(frame: pd.DataFrame, current_idx: int, window: int, tp_pct: float, sl_pct: float) -> ProbabilityLabel | None:
    current = frame.iloc[current_idx]
    close = safe_float(current.get("close"))
    if close is None or close <= 0:
        return None
    future = frame.iloc[current_idx + 1 : current_idx + 1 + window]
    if len(future) < window:
        return None

    tp_price = close * (1 + tp_pct)
    sl_price = close * (1 - sl_pct)
    bars_to_tp: int | None = None
    bars_to_sl: int | None = None

    for offset, (_, row) in enumerate(future.iterrows(), start=1):
        high = safe_float(row.get("high"))
        low = safe_float(row.get("low"))
        if bars_to_tp is None and high is not None and high >= tp_price:
            bars_to_tp = offset
        if bars_to_sl is None and low is not None and low <= sl_price:
            bars_to_sl = offset
        if bars_to_tp is not None or bars_to_sl is not None:
            # Stop once the first event is known. If both happen in one candle,
            # the conservative ordering treats the stop as first.
            if bars_to_sl == offset:
                break
            if bars_to_tp == offset:
                break

    hit_tp_before_sl = bars_to_tp is not None and (bars_to_sl is None or bars_to_tp < bars_to_sl)
    hit_sl_before_tp = bars_to_sl is not None and (bars_to_tp is None or bars_to_sl <= bars_to_tp)
    no_hit = not hit_tp_before_sl and not hit_sl_before_tp

    mfe_pct = ((future["high"].max() / close) - 1) if not future.empty else None
    mae_pct = ((future["low"].min() / close) - 1) if not future.empty else None
    end_close = safe_float(future.iloc[-1].get("close"))
    final_return = (end_close / close - 1) if end_close is not None else None
    if hit_tp_before_sl:
        outcome = tp_pct
    elif hit_sl_before_tp:
        outcome = -sl_pct
    else:
        outcome = final_return

    return ProbabilityLabel(
        windowBars=window,
        hitTpBeforeSl=hit_tp_before_sl,
        hitSlBeforeTp=hit_sl_before_tp,
        noHit=no_hit,
        mfePct=round_optional(mfe_pct),
        maePct=round_optional(mae_pct),
        futureReturnAtWindowEnd=round_optional(final_return),
        barsToTp=bars_to_tp,
        barsToSl=bars_to_sl,
        outcomeReturnPct=round_optional(outcome),
    )


def _btc_state_at(btc_frame: pd.DataFrame | None, timestamp: pd.Timestamp) -> str:
    if btc_frame is None:
        return "unknown"
    idx, row = _row_at_or_after(btc_frame, timestamp)
    if row is None or idx is None or idx < 3:
        return "unknown"
    prior = btc_frame.iloc[idx - 3]
    close = safe_float(row.get("close"))
    prior_close = safe_float(prior.get("close"))
    return_3h = (close / prior_close - 1) if close is not None and prior_close is not None and prior_close > 0 else None
    return btc_state(row.get("close"), row.get("ema200"), return_3h)


def _sample_from_row(
    snapshot: dict[str, Any],
    pair: str,
    row: pd.Series,
    labels: dict[str, ProbabilityLabel],
    score: dict[str, Any],
    btc: str,
    timeframe: str,
) -> ProbabilityCandidateSample:
    close = round_optional(row.get("close"))
    ema20 = round_optional(row.get("ema20"))
    rsi = round_optional(row.get("rsi14"))
    atr_pct = round_optional(row.get("atrPct"))
    sample_id = f"{snapshot.get('snapshotDate')}_{pair.replace('/', '_').replace(':', '_')}_{timeframe}"
    return ProbabilityCandidateSample(
        sampleId=sample_id,
        timestamp=row.get("date").isoformat(),
        pair=pair,
        timeframe=timeframe,
        snapshotDate=str(snapshot.get("snapshotDate")),
        regimeCandidate=regime_candidate(close, ema20, row.get("ema50"), row.get("ema200"), rsi, atr_pct, btc),
        close=close,
        volume=round_optional(row.get("volume"), 4),
        quoteVolume=round_optional(row.get("quoteVolume"), 4),
        rsi14=rsi,
        ema20=ema20,
        ema50=round_optional(row.get("ema50")),
        ema200=round_optional(row.get("ema200")),
        macdHist=round_optional(row.get("macdHist")),
        bbMiddle=round_optional(row.get("bbMiddle")),
        bbUpper=round_optional(row.get("bbUpper")),
        bbLower=round_optional(row.get("bbLower")),
        atrPct=atr_pct,
        volumeRatio=round_optional(row.get("volumeRatio")),
        btcState=btc,
        liquidityBucket=liquidity_bucket(score.get("quoteVolume24h")),
        volatilityBucket=volatility_bucket(atr_pct),
        rsiBucket=rsi_bucket(rsi),
        distanceToEma20Bucket=ema_distance_bucket(close, ema20),
        distanceToBollingerBucket=bollinger_position_bucket(
            close,
            row.get("bbLower"),
            row.get("bbMiddle"),
            row.get("bbUpper"),
        ),
        labels=labels,
    )


def build_probability_samples(config: ProbabilityDatasetConfig) -> ProbabilityDatasetBuild:
    snapshots = [
        snapshot
        for snapshot in read_universe_snapshots(Path(config.universeSnapshotsPath))
        if _snapshot_in_timerange(str(snapshot.get("snapshotDate", "")), config.timerange)
    ]
    selected_pairs = {
        str(pair)
        for snapshot in snapshots
        for pair in snapshot.get("selectedPairs", [])
        if pair
    }
    selected_pairs.add("BTC/USDT:USDT")
    frames, load_errors = _load_frames(config, selected_pairs)
    btc_frame = frames.get("BTC/USDT:USDT")
    samples: list[ProbabilityCandidateSample] = []
    insufficient_data_count = 0
    warnings: list[str] = []
    insufficiency_by_reason: dict[str, int] = defaultdict(int)

    for snapshot in snapshots:
        snapshot_date = str(snapshot.get("snapshotDate"))
        timestamp = pd.Timestamp(datetime.strptime(snapshot_date, "%Y-%m-%d").replace(tzinfo=UTC))
        scores = _pair_score_map(snapshot)
        for pair in snapshot.get("selectedPairs", []):
            frame = frames.get(pair)
            if frame is None:
                insufficient_data_count += 1
                insufficiency_by_reason[f"{pair}: missing_frame"] += 1
                continue
            idx, row = _row_at_or_after(frame, timestamp)
            if row is None or idx is None:
                insufficient_data_count += 1
                insufficiency_by_reason[f"{pair}: missing_current_candle"] += 1
                continue
            labels: dict[str, ProbabilityLabel] = {}
            for window in config.windows:
                label = _future_label(frame, idx, window, config.tpPct, config.slPct)
                if label is not None:
                    labels[str(window)] = label
            if len(labels) != len(config.windows):
                insufficient_data_count += 1
                insufficiency_by_reason[f"{pair}: insufficient_future_window"] += 1
                continue
            btc = _btc_state_at(btc_frame, timestamp)
            samples.append(_sample_from_row(snapshot, str(pair), row, labels, scores.get(str(pair), {}), btc, config.timeframe))

    if load_errors:
        warnings.extend(f"{pair}: {reason}" for pair, reason in sorted(load_errors.items()))
    warnings.extend(f"{reason}: {count}" for reason, count in sorted(insufficiency_by_reason.items()))
    return ProbabilityDatasetBuild(
        samples=samples,
        snapshotCount=len(snapshots),
        insufficientDataCount=insufficient_data_count,
        warnings=warnings,
        pairLoadErrors=load_errors,
    )


def no_lookahead_rules() -> list[str]:
    return [
        "Universe snapshots are read from V13.4.13 and were built with candles closed before snapshotDate 00:00 UTC.",
        "Sample features use only the current candle and rolling indicators calculated from current and prior candles.",
        "Forward windows are used only for labels: hitTpBeforeSl, hitSlBeforeTp, MFE, MAE, and future return.",
        "Forward label values are not written back into feature buckets.",
        "Missing current or future candles are counted as insufficient data instead of being filled with fake values.",
    ]

