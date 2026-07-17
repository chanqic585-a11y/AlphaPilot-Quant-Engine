"""S01 implementation of the shared formal candidate adapter contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from alphapilot.advisory_r_campaign.candidates import build_candidate_inventory
from alphapilot.advisory_r_campaign.signals import replay_candidate
from alphapilot.formal_validation.candidate_adapter import (
    CandidateAdapterIdentityError,
    resolve_candidate_signal_identity,
)
from alphapilot.formal_validation.s01_event_identity import with_s01_signal_id

from .s01_parity import run_s01_formal_adapter_parity


@dataclass(frozen=True)
class S01CandidateAdapter:
    """Keep all S01-specific discovery and execution outside the core."""

    CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"

    candidate_id: str = CANDIDATE_ID
    adapter_id: str = "s01_freqtrade_formal_adapter"
    adapter_version: str = "2"

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
        del direction, expected_entry_timestamp, signal_context
        if candidate_id != self.candidate_id:
            raise CandidateAdapterIdentityError(
                "candidate_id_mismatch:"
                f"event={candidate_id}:adapter={self.candidate_id}"
            )
        identified = with_s01_signal_id(
            {
                "symbol": symbol,
                "signalTimestamp": signal_timestamp,
            }
        )
        return str(identified["signalId"])

    def resolve_candidate(
        self,
        *,
        repo_root: Path,
        preregistration: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del repo_root, preregistration
        candidate = next(
            (
                dict(row)
                for row in build_candidate_inventory()
                if str(row.get("candidateId")) == self.candidate_id
            ),
            None,
        )
        if candidate is None:
            raise KeyError(f"candidate_identity_missing:{self.candidate_id}")
        return candidate

    def replay(
        self,
        *,
        candidate: Mapping[str, Any],
        frames: Mapping[str, pd.DataFrame],
        round_trip_cost_rate: float,
    ) -> Sequence[Mapping[str, Any]]:
        events: list[dict[str, Any]] = []
        for event in replay_candidate(
            candidate,
            frames,
            round_trip_cost_rate=round_trip_cost_rate,
        ):
            identified = dict(event)
            identified["signalId"] = resolve_candidate_signal_identity(
                adapter=self,
                event=identified,
            )
            events.append(identified)
        return events

    def run_parity(
        self,
        *,
        bundle: object,
        repo_root: Path,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        return run_s01_formal_adapter_parity(
            bundle=bundle,
            repo_root=repo_root,
            candidate_adapter=self,
        )
