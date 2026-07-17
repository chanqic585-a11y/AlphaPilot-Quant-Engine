"""Deterministic positive-signal parity fixture for the frozen S01 adapter."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from alphapilot.advisory_r_campaign.candidates import build_candidate_inventory
from alphapilot.advisory_r_campaign.signals import replay_candidate

from .dual_engine_parity import assert_dual_engine_parity


FROZEN_S01_INSTRUMENT_IDS = tuple(
    sorted(
        (
            "AAVE-USDT-SWAP",
            "ADA-USDT-SWAP",
            "ALGO-USDT-SWAP",
            "ATOM-USDT-SWAP",
            "AVAX-USDT-SWAP",
            "BCH-USDT-SWAP",
            "BTC-USDT-SWAP",
            "COMP-USDT-SWAP",
            "DOGE-USDT-SWAP",
            "ETC-USDT-SWAP",
            "ETH-USDT-SWAP",
            "FIL-USDT-SWAP",
            "LINK-USDT-SWAP",
            "LTC-USDT-SWAP",
            "NEO-USDT-SWAP",
            "SOL-USDT-SWAP",
            "TRX-USDT-SWAP",
            "XRP-USDT-SWAP",
            "XTZ-USDT-SWAP",
            "YFI-USDT-SWAP",
        )
    )
)


def _pair(instrument_id: str) -> str:
    return instrument_id.replace("-USDT-SWAP", "/USDT:USDT")


def _instrument(pair: str) -> str:
    return pair.replace("/USDT:USDT", "-USDT-SWAP")


def build_s01_synthetic_fixture() -> dict[str, pd.DataFrame]:
    """Return 20 deterministic 4h frames with one genuine S01 entry."""

    length = 280
    dates = pd.date_range("2025-01-01", periods=length, freq="4h", tz="UTC")
    frames: dict[str, pd.DataFrame] = {}
    for instrument_id in FROZEN_S01_INSTRUMENT_IDS:
        close = np.full(length, 100.0, dtype="float64")
        if instrument_id == "BTC-USDT-SWAP":
            close = np.linspace(140.0, 80.0, length, dtype="float64")
        elif instrument_id == "ETH-USDT-SWAP":
            close[220:225] = [70.0, 75.0, 82.0, 84.0, 86.0]
        frames[instrument_id] = pd.DataFrame(
            {
                "date": dates,
                "open": close,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1000.0,
            }
        )
    return frames


class _SyntheticDataProvider:
    def __init__(self, frames: Mapping[str, pd.DataFrame]) -> None:
        self._frames = {_pair(key): value.copy() for key, value in frames.items()}
        self.requested_pairs: list[str] = []
        self.analyzed: dict[str, pd.DataFrame] = {}

    def current_whitelist(self) -> list[str]:
        return [*sorted(self._frames), "FAKE/USDT:USDT"]

    def get_pair_dataframe(self, *, pair: str, timeframe: str) -> pd.DataFrame:
        if timeframe != "4h":
            raise ValueError("synthetic S01 fixture only supports 4h")
        self.requested_pairs.append(pair)
        return self._frames[pair].copy()

    def get_analyzed_dataframe(self, pair: str, timeframe: str) -> tuple[pd.DataFrame, None]:
        if timeframe != "4h":
            raise ValueError("synthetic S01 fixture only supports 4h")
        return self.analyzed[pair].copy(), None


def _load_strategy(repo_root: Path) -> tuple[Any, Any]:
    path = repo_root / "user_data" / "strategies" / "AlphaPilotS01BearRecovery4H.py"
    spec = importlib.util.spec_from_file_location("alphapilot_s01_phase2_adapter", path)
    if not spec or not spec.loader:
        raise RuntimeError("unable to load frozen S01 Freqtrade adapter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    strategy_type = module.AlphaPilotS01BearRecovery4H
    try:
        strategy = strategy_type(config={"timeframe": "4h", "dry_run": True})
    except TypeError:
        strategy = strategy_type()
    return module, strategy


def _signal_id(symbol: str, timestamp: str) -> str:
    return f"s01_synthetic::{symbol}::{timestamp}"


def _canonical_formal_event(event: Mapping[str, Any]) -> dict[str, Any]:
    legs = []
    for leg_index, leg in enumerate(event["legs"]):
        legs.append(
            {
                "legIndex": leg_index,
                "legFraction": float(leg["fraction"]),
                "exitReason": str(leg["reason"]),
                "triggerTimestamp": str(leg["triggerTimestamp"]),
                "executionTimestamp": str(leg["executionTimestamp"]),
                "price": float(leg["price"]),
                "grossR": float(leg["grossR"]),
                "feesR": float(leg["feesR"]),
                "slippageR": float(leg["slippageR"]),
                "spreadProxyR": float(leg["spreadProxyR"]),
                "fundingR": float(leg["fundingR"]),
                "netR": float(leg["netR"]),
                "isGapFill": bool(leg["isGapFill"]),
                "ambiguousPath": bool(leg["ambiguousPath"]),
            }
        )
    signal_timestamp = str(event["signalTimestamp"])
    return {
        "candidateId": str(event["candidateId"]),
        "signalId": _signal_id(str(event["symbol"]), signal_timestamp),
        "symbol": str(event["symbol"]),
        "direction": str(event["direction"]),
        "signalTimestamp": signal_timestamp,
        "entryTimestamp": str(event["entryTimestamp"]),
        "entryPrice": float(event["entryPrice"]),
        "initialStop": float(event["initialStopPrice"]),
        "exitPolicyHash": str(event["exitPolicyHash"]),
        "exitLegCount": len(legs),
        "exitLegs": legs,
    }


def _leg(
    *,
    frame: pd.DataFrame,
    entry_position: int,
    entry_price: float,
    risk_distance: float,
    fraction: float,
    reason: str,
    trigger_position: int,
    execution_position: int,
    price: float,
    is_gap_fill: bool = False,
    ambiguous_path: bool = False,
) -> dict[str, Any]:
    gross_r = (price - entry_price) / risk_distance * fraction
    price_scale = (entry_price + abs(price)) / risk_distance * fraction
    fees_r = price_scale * 2.5 / 10_000
    slippage_r = price_scale * 1.25 / 10_000
    spread_r = price_scale * 1.25 / 10_000
    return {
        "legFraction": float(fraction),
        "exitReason": reason,
        "triggerTimestamp": pd.Timestamp(frame.iloc[trigger_position]["date"]).isoformat(),
        "executionTimestamp": pd.Timestamp(
            frame.iloc[execution_position]["date"]
        ).isoformat(),
        "price": float(price),
        "grossR": float(gross_r),
        "feesR": float(fees_r),
        "slippageR": float(slippage_r),
        "spreadProxyR": float(spread_r),
        "fundingR": 0.0,
        "netR": float(gross_r - fees_r - slippage_r - spread_r),
        "isGapFill": is_gap_fill,
        "ambiguousPath": ambiguous_path,
    }


def _simulate_adapter_event(
    *,
    strategy: Any,
    candidate: Mapping[str, Any],
    symbol: str,
    frame: pd.DataFrame,
    signal_position: int,
) -> dict[str, Any]:
    entry_position = signal_position + 1
    entry_price = float(frame.iloc[entry_position]["open"])
    atr = float(frame.iloc[signal_position]["s01_atr14"])
    if not math.isfinite(atr) or atr <= 0:
        raise RuntimeError("adapter entry is missing signal-candle ATR")
    risk_distance = atr * float(strategy.initial_stop_atr_multiple)
    initial_stop = entry_price - risk_distance
    partial_target = entry_price + risk_distance * float(strategy.partial_at_r)
    remaining = 1.0
    partial_taken = False
    legs: list[dict[str, Any]] = []
    last_position = min(
        len(frame) - 1,
        entry_position + int(strategy.maximum_hold_bars) - 1,
    )
    for position in range(entry_position, last_position + 1):
        row = frame.iloc[position]
        open_price = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        if open_price <= initial_stop:
            legs.append(
                _leg(
                    frame=frame,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=risk_distance,
                    fraction=remaining,
                    reason="stop_loss" if position == entry_position else "stop_gap",
                    trigger_position=position,
                    execution_position=position,
                    price=open_price,
                    is_gap_fill=position > entry_position,
                )
            )
            remaining = 0.0
            break
        partial_hit = not partial_taken and high >= partial_target
        if low <= initial_stop:
            legs.append(
                _leg(
                    frame=frame,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=risk_distance,
                    fraction=remaining,
                    reason="stop_loss",
                    trigger_position=position,
                    execution_position=position,
                    price=initial_stop,
                    ambiguous_path=partial_hit,
                )
            )
            remaining = 0.0
            break
        if not partial_taken and open_price >= partial_target:
            fraction = float(strategy.partial_fraction)
            legs.append(
                _leg(
                    frame=frame,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=risk_distance,
                    fraction=fraction,
                    reason="partial_gap",
                    trigger_position=position,
                    execution_position=position,
                    price=partial_target,
                    is_gap_fill=True,
                )
            )
            remaining -= fraction
            partial_taken = True
        elif partial_hit:
            fraction = float(strategy.partial_fraction)
            legs.append(
                _leg(
                    frame=frame,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=risk_distance,
                    fraction=fraction,
                    reason="partial_target",
                    trigger_position=position,
                    execution_position=position,
                    price=partial_target,
                )
            )
            remaining -= fraction
            partial_taken = True
        if bool(frame.iloc[position]["s01_structure_exit"]):
            execution_position = min(position + 1, len(frame) - 1)
            exit_price = (
                float(frame.iloc[execution_position]["open"])
                if execution_position > position
                else close
            )
            legs.append(
                _leg(
                    frame=frame,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=risk_distance,
                    fraction=remaining,
                    reason="structure_exit",
                    trigger_position=position,
                    execution_position=execution_position,
                    price=exit_price,
                )
            )
            remaining = 0.0
            break
        if position == last_position:
            execution_position = min(position + 1, len(frame) - 1)
            exit_price = (
                float(frame.iloc[execution_position]["open"])
                if execution_position > position
                else close
            )
            legs.append(
                _leg(
                    frame=frame,
                    entry_position=entry_position,
                    entry_price=entry_price,
                    risk_distance=risk_distance,
                    fraction=remaining,
                    reason="maximum_hold",
                    trigger_position=position,
                    execution_position=execution_position,
                    price=exit_price,
                )
            )
            remaining = 0.0
    if not legs or not math.isclose(remaining, 0.0, abs_tol=1e-12):
        raise RuntimeError("adapter contract simulator did not close the event")
    for index, leg in enumerate(legs):
        leg["legIndex"] = index
    signal_timestamp = pd.Timestamp(frame.iloc[signal_position]["date"]).isoformat()
    return {
        "candidateId": str(candidate["candidateId"]),
        "signalId": _signal_id(symbol, signal_timestamp),
        "symbol": symbol,
        "direction": "long",
        "signalTimestamp": signal_timestamp,
        "entryTimestamp": pd.Timestamp(frame.iloc[entry_position]["date"]).isoformat(),
        "entryPrice": entry_price,
        "initialStop": initial_stop,
        "exitPolicyHash": str(candidate["exitPolicyHash"]),
        "exitLegCount": len(legs),
        "exitLegs": legs,
    }


def run_s01_synthetic_parity(repo_root: Path) -> dict[str, Any]:
    frames = build_s01_synthetic_fixture()
    candidate = next(
        row for row in build_candidate_inventory() if row["candidateId"]
        == "s01_bear_idiosyncratic_selloff_recovery_4h"
    )
    formal_events = replay_candidate(candidate, frames, round_trip_cost_rate=0.001)
    reference_events = [_canonical_formal_event(event) for event in formal_events]

    module, strategy = _load_strategy(Path(repo_root).resolve())
    if tuple(sorted(module.FROZEN_S01_INSTRUMENT_IDS)) != FROZEN_S01_INSTRUMENT_IDS:
        raise RuntimeError("adapter frozen universe differs from preregistration")
    provider = _SyntheticDataProvider(frames)
    strategy.dp = provider
    adapter_events: list[dict[str, Any]] = []
    adapter_signal_count = 0
    for instrument_id, raw_frame in sorted(frames.items()):
        pair = _pair(instrument_id)
        analyzed = strategy.populate_indicators(raw_frame.copy(), {"pair": pair})
        analyzed = strategy.populate_entry_trend(analyzed, {"pair": pair})
        provider.analyzed[pair] = analyzed.copy()
        positions = np.flatnonzero(
            pd.to_numeric(analyzed.get("enter_long", 0), errors="coerce")
            .fillna(0)
            .eq(1)
            .to_numpy()
        )
        adapter_signal_count += len(positions)
        next_available = 0
        for signal_position in positions:
            if signal_position < next_available or signal_position >= len(analyzed) - 1:
                continue
            event = _simulate_adapter_event(
                strategy=strategy,
                candidate=candidate,
                symbol=_instrument(pair),
                frame=analyzed,
                signal_position=int(signal_position),
            )
            adapter_events.append(event)
            final_timestamp = event["exitLegs"][-1]["executionTimestamp"]
            matching = analyzed.index[
                pd.to_datetime(analyzed["date"], utc=True)
                == pd.Timestamp(final_timestamp)
            ]
            next_available = int(matching[0]) + 1 if len(matching) else len(analyzed)

    report = assert_dual_engine_parity(reference_events, adapter_events)
    requested_ids = sorted({_instrument(pair) for pair in provider.requested_pairs})
    report.update(
        {
            "actualStrategyAdapterInvoked": True,
            "adapterRuntimeBase": type(strategy).__mro__[1].__module__,
            "frozenUniverseCount": len(FROZEN_S01_INSTRUMENT_IDS),
            "formalSignalCount": len(formal_events),
            "adapterSignalCount": adapter_signal_count,
            "runtimeWhitelistIgnored": "FAKE-USDT-SWAP" not in requested_ids,
            "adapterContextPairs": requested_ids,
            "coveredExitReasons": sorted(
                {
                    str(leg["exitReason"])
                    for event in adapter_events
                    for leg in event["exitLegs"]
                }
            ),
            "syntheticFixtureOnly": True,
            "networkAccessCount": 0,
            "lockedOosAccessCount": 0,
            "credentialReadCount": 0,
            "formalPerformanceClaimed": False,
        }
    )
    return report
