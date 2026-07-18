"""Candidate-neutral fixture proving the formal adapter boundary is reusable."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from alphapilot.formal_validation.candidate_adapter import (
    CandidateAdapterIdentityError,
    resolve_candidate_signal_identity,
)


@dataclass(frozen=True)
class SyntheticCandidateAdapter:
    """Small deterministic adapter used only for architecture certification."""

    candidate_id: str = "synthetic_candidate_fixture_02"
    adapter_id: str = "synthetic_candidate_fixture_adapter"
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
        del direction, expected_entry_timestamp, signal_context
        if candidate_id != self.candidate_id:
            raise CandidateAdapterIdentityError(
                f"candidate_id_mismatch:event={candidate_id}:adapter={self.candidate_id}"
            )
        return f"{candidate_id}::fixture::{symbol}::{signal_timestamp}"

    def resolve_candidate(
        self,
        *,
        repo_root: Path,
        preregistration: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        del repo_root
        return {
            "candidateId": self.candidate_id,
            "strategyDefinitionHash": preregistration.get("strategyDefinitionHash"),
            "exitPolicyHash": preregistration.get("exitPolicyHash"),
            "fixtureOnly": True,
        }

    def replay(
        self,
        *,
        candidate: Mapping[str, Any],
        frames: Mapping[str, pd.DataFrame],
        round_trip_cost_rate: float,
    ) -> Sequence[Mapping[str, Any]]:
        events: list[dict[str, Any]] = []
        for symbol in sorted(frames):
            frame = frames[symbol]
            if frame.empty:
                continue
            timestamp = pd.Timestamp(frame.iloc[0]["date"]).isoformat()
            event = {
                "candidateId": str(candidate["candidateId"]),
                "symbol": symbol,
                "direction": "long",
                "signalTimestamp": timestamp,
                "entryTimestamp": timestamp,
                "netR": -float(round_trip_cost_rate),
                "fixtureOnly": True,
            }
            event["signalId"] = resolve_candidate_signal_identity(
                adapter=self,
                event=event,
            )
            events.append(event)
        return events

    def run_parity(
        self,
        *,
        bundle: object,
        repo_root: Path,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        del bundle, repo_root
        report = {
            "schemaVersion": "synthetic_candidate_parity_v1",
            "status": "passed",
            "passed": True,
            "fixtureOnly": True,
        }
        return report, [], []


__all__ = ["SyntheticCandidateAdapter"]
