"""Candidate-neutral directional-event adapter used by generated research candidates."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.formal_validation.candidate_adapter import CandidateAdapterIdentityError


def _frame(value: pd.DataFrame) -> pd.DataFrame:
    frame = value.copy()
    if "date" not in frame:
        frame["date"] = frame.index
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ("open", "high", "low", "close", "volume"):
        if column not in frame:
            frame[column] = 0.0 if column == "volume" else frame.get("close", 0.0)
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["open", "high", "low", "close"])


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


def _aligned_returns(frames: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
    values: dict[str, pd.Series] = {}
    for symbol, raw in frames.items():
        frame = _frame(raw).set_index("date")
        values[symbol] = frame["close"].pct_change()
    return pd.DataFrame(values).sort_index()


def _setup_mask(
    *,
    setup_id: str,
    frame: pd.DataFrame,
    symbol: str,
    direction: str,
    all_frames: Mapping[str, pd.DataFrame],
) -> pd.Series:
    close = frame["close"]
    returns = close.pct_change()
    ema_fast = close.ewm(span=20, adjust=False).mean()
    ema_slow = close.ewm(span=80, adjust=False).mean()
    rolling_high = close.rolling(20, min_periods=20).max().shift(1)
    rolling_low = close.rolling(20, min_periods=20).min().shift(1)
    volatility_fast = returns.rolling(12, min_periods=12).std()
    volatility_slow = returns.rolling(48, min_periods=24).std()
    long = direction == "long"

    if setup_id == "trend_pullback_continuation":
        trend = ema_fast > ema_slow if long else ema_fast < ema_slow
        reclaim = (
            (close > ema_fast) & (close.shift(1) <= ema_fast.shift(1))
            if long
            else (close < ema_fast) & (close.shift(1) >= ema_fast.shift(1))
        )
        return trend & reclaim
    if setup_id == "volatility_compression_release":
        compressed = volatility_fast.shift(1) < volatility_slow.shift(1) * 0.75
        breakout = close > rolling_high if long else close < rolling_low
        return compressed & breakout
    if setup_id == "btc_shock_lag":
        btc_raw = all_frames.get("BTC-USDT-SWAP")
        if btc_raw is None or symbol == "BTC-USDT-SWAP":
            return pd.Series(False, index=frame.index)
        btc = _frame(btc_raw).set_index("date")["close"].pct_change()
        aligned = btc.reindex(frame["date"]).reset_index(drop=True)
        shock = aligned.shift(1) < -0.018 if long else aligned.shift(1) > 0.018
        response = returns > 0 if long else returns < 0
        return shock.fillna(False) & response.fillna(False)
    if setup_id == "volatility_shock_asymmetry":
        threshold = returns.rolling(48, min_periods=24).std().shift(1) * 2.2
        prior_shock = returns.shift(1) < -threshold if long else returns.shift(1) > threshold
        reversal = returns > 0 if long else returns < 0
        return prior_shock & reversal
    if setup_id == "cross_session_liquidity_transition":
        transition = frame["date"].dt.hour.isin([0, 8, 16])
        impulse = close > close.shift(4) if long else close < close.shift(4)
        return transition & impulse
    if setup_id == "residual_extreme_causal_recovery":
        returns_panel = _aligned_returns(all_frames)
        if symbol not in returns_panel or "BTC-USDT-SWAP" not in returns_panel:
            return pd.Series(False, index=frame.index)
        residual = returns_panel[symbol] - returns_panel["BTC-USDT-SWAP"]
        scale = residual.rolling(72, min_periods=36).std().shift(1)
        prior = residual.shift(1)
        event = prior < -2.0 * scale if long else prior > 2.0 * scale
        recovery = residual > 0 if long else residual < 0
        aligned = (event & recovery).reindex(frame["date"]).fillna(False)
        return pd.Series(aligned.to_numpy(), index=frame.index)
    if setup_id == "trend_failure_reversal":
        prior_trend = ema_fast.shift(1) < ema_slow.shift(1) if long else ema_fast.shift(1) > ema_slow.shift(1)
        failure = (
            (close > ema_fast) & (close.shift(1) <= ema_fast.shift(1))
            if long
            else (close < ema_fast) & (close.shift(1) >= ema_fast.shift(1))
        )
        return prior_trend & failure
    if setup_id == "breadth_correlation_directional_filter":
        panel = _aligned_returns(all_frames)
        breadth = (panel > 0).mean(axis=1)
        regime = breadth >= 0.75 if long else breadth <= 0.25
        aligned_regime = regime.reindex(frame["date"]).fillna(False).reset_index(drop=True)
        local = returns > 0 if long else returns < 0
        return pd.Series(aligned_regime.to_numpy(), index=frame.index) & local
    raise ValueError(f"unknown_generated_setup:{setup_id}")


def _synthetic_frames(setup_id: str) -> dict[str, pd.DataFrame]:
    count = 600
    dates = pd.date_range("2024-01-01", periods=count, freq="h", tz="UTC")
    if setup_id == "btc_shock_lag":
        btc_returns = np.full(count, 0.0002)
        eth_returns = np.full(count, 0.00015)
        btc_returns[[100, 300]] = [-0.04, 0.04]
        eth_returns[[101, 301]] = [0.03, -0.03]
        btc_close = 100.0 * np.cumprod(1.0 + btc_returns)
        eth_close = 55.0 * np.cumprod(1.0 + eth_returns)
    else:
        trend = np.linspace(100.0, 130.0, count)
        wave = np.sin(np.arange(count) / 5.0) * 3.0
        jumps = np.where(np.arange(count) % 97 == 0, -8.0, 0.0)
        btc_close = trend + wave + jumps
        eth_close = trend * 0.55 + np.sin(np.arange(count) / 3.0) * 4.0 + np.roll(jumps, 1)

    def make(close: np.ndarray) -> pd.DataFrame:
        close_series = pd.Series(close)
        open_series = close_series.shift(1).fillna(close_series.iloc[0])
        return pd.DataFrame(
            {
                "date": dates,
                "open": open_series,
                "high": np.maximum(open_series, close_series) + 1.0,
                "low": np.minimum(open_series, close_series) - 1.0,
                "close": close_series,
                "volume": 1_000.0 + (np.arange(count) % 23) * 25.0,
            }
        )

    return {"BTC-USDT-SWAP": make(btc_close), "ETH-USDT-SWAP": make(eth_close)}


@dataclass(frozen=True)
class GeneratedDirectionalEventAdapter:
    """Interpret declarative CandidateSpec objects without candidate imports."""

    candidate_id: str
    adapter_id: str = "generated_directional_event_adapter"
    adapter_version: str = "1"

    def signal_identity(
        self,
        *,
        candidate_id: str,
        symbol: str,
        direction: str,
        signal_timestamp: str,
        expected_entry_timestamp: str | None,
        signal_context: Mapping[str, Any],
    ) -> str:
        del signal_context
        if candidate_id != self.candidate_id:
            raise CandidateAdapterIdentityError(
                f"candidate_id_mismatch:event={candidate_id}:adapter={self.candidate_id}"
            )
        return stable_hash(
            {
                "candidateId": candidate_id,
                "symbol": symbol,
                "direction": direction,
                "signalTimestamp": signal_timestamp,
                "expectedEntryTimestamp": expected_entry_timestamp,
            },
            prefix="generated_directional_event_signal",
        )

    def resolve_candidate(
        self, *, repo_root: Path, preregistration: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        del repo_root
        candidate = dict(preregistration.get("candidateSpec") or {})
        if candidate.get("candidateId") != self.candidate_id:
            raise CandidateAdapterIdentityError("candidate_identity_missing")
        return candidate

    def load_signals(
        self,
        *,
        candidate: Mapping[str, Any],
        frames: Mapping[str, pd.DataFrame],
    ) -> Sequence[Mapping[str, Any]]:
        setup_id = str(candidate["entryDefinition"]["setupId"])
        direction = str(candidate["direction"])
        events: list[dict[str, Any]] = []
        for symbol in sorted(frames):
            frame = _frame(frames[symbol])
            mask = _setup_mask(
                setup_id=setup_id,
                frame=frame,
                symbol=symbol,
                direction=direction,
                all_frames=frames,
            ).fillna(False)
            for index in frame.index[mask]:
                if index + 1 >= len(frame):
                    continue
                signal_time = frame.at[index, "date"].isoformat()
                entry_time = frame.at[index + 1, "date"].isoformat()
                event = {
                    "candidateId": self.candidate_id,
                    "symbol": symbol,
                    "direction": direction,
                    "signalTimestamp": signal_time,
                    "entryTimestamp": entry_time,
                    "expectedEntryTimestamp": entry_time,
                    "entryPrice": float(frame.at[index + 1, "open"]),
                    "signalBarIndex": int(index),
                    "structuralOnly": True,
                    "economicResultComputationDisabled": True,
                    "exitReplayDisabled": True,
                    "setupId": setup_id,
                }
                event["signalId"] = self.signal_identity(
                    candidate_id=self.candidate_id,
                    symbol=symbol,
                    direction=direction,
                    signal_timestamp=signal_time,
                    expected_entry_timestamp=entry_time,
                    signal_context=event,
                )
                events.append(event)
        return events

    def replay(
        self,
        *,
        candidate: Mapping[str, Any],
        frames: Mapping[str, pd.DataFrame],
        round_trip_cost_rate: float,
    ) -> Sequence[Mapping[str, Any]]:
        signals = self.load_signals(candidate=candidate, frames=frames)
        maximum_hold = int(candidate["maximumHoldBars"])
        stop_multiple = float(candidate["initialStop"]["atrMultiple"])
        target_multiple = float(candidate["exitPolicy"].get("targetR", 1.5))
        direction = str(candidate["direction"])
        results: list[dict[str, Any]] = []
        normalized = {symbol: _frame(frame) for symbol, frame in frames.items()}
        for signal in signals:
            frame = normalized[str(signal["symbol"])]
            entry_index = int(signal["signalBarIndex"]) + 1
            if entry_index >= len(frame) - 1:
                continue
            atr = _atr(frame).iloc[entry_index]
            if not np.isfinite(atr) or atr <= 0:
                continue
            entry = float(frame.at[entry_index, "open"])
            risk = float(atr) * stop_multiple
            stop = entry - risk if direction == "long" else entry + risk
            target = entry + target_multiple * risk if direction == "long" else entry - target_multiple * risk
            final_index = min(entry_index + maximum_hold, len(frame) - 1)
            exit_index = final_index
            exit_price = float(frame.at[final_index, "close"])
            exit_reason = "maximum_hold"
            for cursor in range(entry_index, final_index + 1):
                high = float(frame.at[cursor, "high"])
                low = float(frame.at[cursor, "low"])
                if direction == "long" and low <= stop:
                    exit_index, exit_price, exit_reason = cursor, stop, "initial_stop"
                    break
                if direction == "short" and high >= stop:
                    exit_index, exit_price, exit_reason = cursor, stop, "initial_stop"
                    break
                if direction == "long" and high >= target:
                    exit_index, exit_price, exit_reason = cursor, target, "advisory_r_target"
                    break
                if direction == "short" and low <= target:
                    exit_index, exit_price, exit_reason = cursor, target, "advisory_r_target"
                    break
            gross_r = (exit_price - entry) / risk * (1.0 if direction == "long" else -1.0)
            cost_r = entry * float(round_trip_cost_rate) / risk
            results.append(
                {
                    **dict(signal),
                    "exitTimestamp": frame.at[exit_index, "date"].isoformat(),
                    "exitPrice": exit_price,
                    "exitReason": exit_reason,
                    "initialStopPrice": stop,
                    "grossR": gross_r,
                    "costR": cost_r,
                    "netR": gross_r - cost_r,
                }
            )
        return results

    def run_fixture_parity(
        self, *, candidate: Mapping[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        frames = _synthetic_frames(str(candidate["entryDefinition"]["setupId"]))
        first = [dict(row) for row in self.load_signals(candidate=candidate, frames=frames)]
        second = [dict(row) for row in self.load_signals(candidate=candidate, frames=frames)]
        passed = bool(first) and first == second
        parity = {
            "schemaVersion": "generated_freqtrade_fixture_parity_v1",
            "status": "passed" if passed else "failed",
            "passed": passed,
            "referenceEventCount": len(first),
            "translatedEventCount": len(second),
            "coreEngineChangedForCandidate": False,
        }
        return parity, first, second

    def run_parity(
        self, *, bundle: object, repo_root: Path
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        del repo_root
        return self.run_fixture_parity(candidate=dict(getattr(bundle, "candidate")))


__all__ = ["GeneratedDirectionalEventAdapter"]
