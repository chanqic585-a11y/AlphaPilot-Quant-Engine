"""S01-specific formal parity execution behind the candidate adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from alphapilot.advisory_r_campaign.signals import replay_candidate
from alphapilot.formal_validation.candidate_adapter import CandidateAdapter
from alphapilot.formal_validation.formal_input import FormalInputBundle
from alphapilot.formal_validation.formal_parity import (
    canonicalize_formal_event,
    summarize_formal_parity,
)
from alphapilot.formal_validation.s01_dual_engine_audit import (
    _load_strategy,
    _simulate_adapter_event,
)


def _pair(instrument_id: str) -> str:
    return instrument_id.replace("-USDT-SWAP", "/USDT:USDT")


def _instrument(pair: str) -> str:
    return pair.replace("/USDT:USDT", "-USDT-SWAP")


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
    candidate_adapter: CandidateAdapter,
    require_freqtrade_runtime: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Run the S01 adapter against all frozen real-input partitions."""

    round_trip_cost = float(bundle.preregistration["costModel"]["baseRoundTripCostRate"])
    raw_reference = replay_candidate(
        bundle.candidate,
        bundle.frames,
        round_trip_cost_rate=round_trip_cost,
    )
    reference_events = [
        canonicalize_formal_event(event, candidate_adapter=candidate_adapter)
        for event in raw_reference
    ]

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
            adapter_events.append(
                canonicalize_formal_event(
                    event,
                    candidate_adapter=candidate_adapter,
                )
            )
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
        schema_version="s01_formal_translation_parity_v1",
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
