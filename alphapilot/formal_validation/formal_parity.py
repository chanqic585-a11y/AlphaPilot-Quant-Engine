"""Real-input translation parity for the frozen S01 Freqtrade adapter."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from alphapilot.advisory_r_campaign.signals import replay_candidate

from .dual_engine_parity import evaluate_dual_engine_parity
from .formal_input import FormalInputBundle
from .s01_dual_engine_audit import _load_strategy, _simulate_adapter_event


def _pair(instrument_id: str) -> str:
    return instrument_id.replace("-USDT-SWAP", "/USDT:USDT")


def _instrument(pair: str) -> str:
    return pair.replace("/USDT:USDT", "-USDT-SWAP")


def _signal_id(symbol: str, timestamp: str) -> str:
    return f"s01_formal::{symbol}::{timestamp}"


def canonicalize_formal_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Map an internal replay event to the strict parity contract."""

    legs: list[dict[str, Any]] = []
    for leg_index, raw_leg in enumerate(event.get("legs") or event.get("exitLegs") or []):
        leg = dict(raw_leg)
        legs.append(
            {
                "legIndex": int(leg.get("legIndex", leg_index)),
                "legFraction": float(leg.get("legFraction", leg.get("fraction"))),
                "exitReason": str(leg.get("exitReason", leg.get("reason"))),
                "triggerTimestamp": str(leg["triggerTimestamp"]),
                "executionTimestamp": str(leg["executionTimestamp"]),
                "price": float(leg["price"]),
                "grossR": float(leg["grossR"]),
                "feesR": float(leg["feesR"]),
                "slippageR": float(leg["slippageR"]),
                "spreadProxyR": float(leg["spreadProxyR"]),
                "fundingR": float(leg.get("fundingR") or 0.0),
                "netR": float(leg["netR"]),
                "isGapFill": bool(leg["isGapFill"]),
                "ambiguousPath": bool(leg["ambiguousPath"]),
            }
        )
    signal_timestamp = str(event["signalTimestamp"])
    symbol = str(event["symbol"])
    initial_stop = event.get("initialStop", event.get("initialStopPrice"))
    return {
        "candidateId": str(event["candidateId"]),
        "signalId": str(event.get("signalId") or _signal_id(symbol, signal_timestamp)),
        "symbol": symbol,
        "direction": str(event.get("direction") or event.get("side")),
        "signalTimestamp": signal_timestamp,
        "entryTimestamp": str(event["entryTimestamp"]),
        "entryPrice": float(event["entryPrice"]),
        "initialStop": float(initial_stop),
        "exitPolicyHash": str(event["exitPolicyHash"]),
        "exitLegCount": len(legs),
        "exitLegs": legs,
    }


def summarize_formal_parity(
    reference_events: Sequence[Mapping[str, Any]],
    adapter_events: Sequence[Mapping[str, Any]],
    *,
    adapter_runtime_base: str,
    require_freqtrade_runtime: bool,
) -> dict[str, Any]:
    """Evaluate strict event parity and fail closed outside Freqtrade."""

    report = evaluate_dual_engine_parity(reference_events, adapter_events)
    runtime_loaded = str(adapter_runtime_base).startswith("freqtrade.")
    blockers = list(report["blockers"])
    if require_freqtrade_runtime and not runtime_loaded:
        blockers.append("freqtrade_runtime_not_loaded")
    blockers = list(dict.fromkeys(blockers))
    event_denominator = max(
        int(report["referenceEventCount"]), int(report["implementationEventCount"]), 1
    )
    expected_leg_count = sum(
        int(event.get("exitLegCount") or 0) for event in reference_events
    )
    identity_pct = float(report["matchedEventCount"]) / event_denominator * 100.0
    leg_pct = (
        float(report["matchedLegCount"]) / expected_leg_count * 100.0
        if expected_leg_count
        else 0.0
    )
    status = "passed" if not blockers else (
        "blocked" if blockers == ["freqtrade_runtime_not_loaded"] else "failed"
    )
    return {
        **report,
        "schemaVersion": "s01_formal_translation_parity_v1",
        "status": status,
        "passed": status == "passed",
        "blockers": blockers,
        "identityParityPct": identity_pct,
        "exitLegParityPct": leg_pct,
        "actualStrategyAdapterInvoked": True,
        "adapterRuntimeBase": str(adapter_runtime_base),
        "freqtradeRuntimeLoaded": runtime_loaded,
        "fullFormalInput": True,
        "syntheticFixtureOnly": False,
        "networkAccessCount": 0,
        "lockedOosAccessCount": 0,
        "credentialReadCount": 0,
        "formalPerformanceClaimed": False,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


class _FormalDataProvider:
    def __init__(self, frames: Mapping[str, pd.DataFrame]) -> None:
        self._frames = {_pair(key): value.copy() for key, value in frames.items()}
        self.requested_pairs: list[str] = []
        self.analyzed: dict[str, pd.DataFrame] = {}

    def current_whitelist(self) -> list[str]:
        return sorted(self._frames)

    def get_pair_dataframe(self, *, pair: str, timeframe: str) -> pd.DataFrame:
        if timeframe != "4h":
            raise ValueError("frozen S01 formal parity only supports 4h")
        self.requested_pairs.append(pair)
        return self._frames[pair].copy()

    def get_analyzed_dataframe(
        self, pair: str, timeframe: str
    ) -> tuple[pd.DataFrame, None]:
        if timeframe != "4h":
            raise ValueError("frozen S01 formal parity only supports 4h")
        return self.analyzed[pair].copy(), None


def run_s01_formal_adapter_parity(
    *,
    bundle: FormalInputBundle,
    repo_root: Path,
    require_freqtrade_runtime: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Run the actual adapter against all frozen real-input partitions."""

    round_trip_cost = float(bundle.preregistration["costModel"]["baseRoundTripCostRate"])
    raw_reference = replay_candidate(
        bundle.candidate,
        bundle.frames,
        round_trip_cost_rate=round_trip_cost,
    )
    reference_events = [canonicalize_formal_event(event) for event in raw_reference]

    module, strategy = _load_strategy(Path(repo_root).resolve())
    frozen_ids = tuple(sorted(str(value) for value in module.FROZEN_S01_INSTRUMENT_IDS))
    expected_ids = tuple(sorted(bundle.frames))
    if frozen_ids != expected_ids:
        raise RuntimeError("adapter frozen universe differs from preregistration")
    provider = _FormalDataProvider(bundle.frames)
    strategy.dp = provider
    adapter_events: list[dict[str, Any]] = []
    adapter_signal_count = 0
    for instrument_id, raw_frame in sorted(bundle.frames.items()):
        pair = _pair(instrument_id)
        analyzed = strategy.populate_indicators(raw_frame.copy(), {"pair": pair})
        analyzed = strategy.populate_entry_trend(analyzed, {"pair": pair})
        provider.analyzed[pair] = analyzed.copy()
        entry = pd.to_numeric(analyzed.get("enter_long", 0), errors="coerce")
        positions = np.flatnonzero(entry.fillna(0).eq(1).to_numpy())
        adapter_signal_count += len(positions)
        next_available = 0
        for signal_position in positions:
            if signal_position < next_available or signal_position >= len(analyzed) - 1:
                continue
            event = _simulate_adapter_event(
                strategy=strategy,
                candidate=bundle.candidate,
                symbol=_instrument(pair),
                frame=analyzed,
                signal_position=int(signal_position),
            )
            event["signalId"] = _signal_id(
                str(event["symbol"]), str(event["signalTimestamp"])
            )
            adapter_events.append(canonicalize_formal_event(event))
            final_timestamp = event["exitLegs"][-1]["executionTimestamp"]
            matching = analyzed.index[
                pd.to_datetime(analyzed["date"], utc=True)
                == pd.Timestamp(final_timestamp)
            ]
            next_available = int(matching[0]) + 1 if len(matching) else len(analyzed)

    runtime_base = type(strategy).__mro__[1].__module__
    report = summarize_formal_parity(
        reference_events,
        adapter_events,
        adapter_runtime_base=runtime_base,
        require_freqtrade_runtime=require_freqtrade_runtime,
    )
    report.update(
        {
            "campaignId": bundle.preregistration["campaignId"],
            "candidateId": bundle.candidate["candidateId"],
            "frozenUniverseCount": len(expected_ids),
            "formalSignalCount": len(raw_reference),
            "adapterSignalCount": adapter_signal_count,
            "adapterContextPairs": sorted(
                {_instrument(pair) for pair in provider.requested_pairs}
            ),
        }
    )
    return report, reference_events, adapter_events


def write_formal_parity_mismatches(path: Path, report: Mapping[str, Any]) -> Path:
    """Write bounded mismatch details without recomputing any event."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("primaryKey", "duplicateIndex", "reasons"),
        )
        writer.writeheader()
        for row in report.get("mismatches", []):
            writer.writerow(
                {
                    "primaryKey": "|".join(str(value) for value in row["primaryKey"]),
                    "duplicateIndex": row["duplicateIndex"],
                    "reasons": "|".join(str(value) for value in row["reasons"]),
                }
            )
    return path
