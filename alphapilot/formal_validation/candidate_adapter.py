"""Candidate-neutral contract for formal validation engines."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

import pandas as pd


class CandidateAdapterIdentityError(ValueError):
    """Raised when CLI, preregistration, and adapter identities diverge."""


class CandidateAdapterContractError(RuntimeError):
    """Raised when an adapter omits a required formal-validation capability."""


@runtime_checkable
class CandidateAdapter(Protocol):
    """Boundary between a candidate implementation and the formal core."""

    candidate_id: str
    adapter_id: str
    adapter_version: str

    def signal_identity(
        self,
        *,
        candidate_id: str,
        symbol: str,
        direction: str,
        signal_timestamp: str,
        expected_entry_timestamp: str | None,
        signal_context: Mapping[str, Any],
    ) -> str: ...

    def resolve_candidate(
        self,
        *,
        repo_root: Path,
        preregistration: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...

    def replay(
        self,
        *,
        candidate: Mapping[str, Any],
        frames: Mapping[str, pd.DataFrame],
        round_trip_cost_rate: float,
    ) -> Sequence[Mapping[str, Any]]: ...

    def run_parity(
        self,
        *,
        bundle: object,
        repo_root: Path,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]: ...

    def build_formal_ranking_evidence(
        self,
        *,
        events: Sequence[Mapping[str, Any]],
        frames: Mapping[str, pd.DataFrame],
        candidate: Mapping[str, Any],
        include_source_bar_hashes: bool = False,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]: ...

    def build_formal_benchmark(
        self,
        *,
        events: Sequence[Mapping[str, Any]],
        frames: Mapping[str, pd.DataFrame],
        preregistration: Mapping[str, Any],
    ) -> dict[str, Any]: ...


def resolve_candidate_signal_identity(
    *,
    adapter: CandidateAdapter,
    event: Mapping[str, Any],
) -> str:
    """Resolve a signal ID through the candidate adapter or fail closed."""

    identity_resolver = getattr(adapter, "signal_identity", None)
    if not callable(identity_resolver):
        raise CandidateAdapterContractError("candidate_adapter_contract_incomplete")

    candidate_id = str(event.get("candidateId") or "").strip()
    symbol = str(event.get("symbol") or "").strip()
    direction = str(event.get("direction") or event.get("side") or "").strip()
    signal_timestamp = str(event.get("signalTimestamp") or "").strip()
    expected_entry_timestamp = str(event.get("entryTimestamp") or "").strip() or None
    if not candidate_id or not symbol or not direction or not signal_timestamp:
        raise CandidateAdapterContractError("candidate_adapter_contract_incomplete")
    if candidate_id != str(adapter.candidate_id or "").strip():
        raise CandidateAdapterIdentityError(
            "candidate_id_mismatch:"
            f"event={candidate_id}:adapter={adapter.candidate_id}"
        )

    signal_id = str(
        identity_resolver(
            candidate_id=candidate_id,
            symbol=symbol,
            direction=direction,
            signal_timestamp=signal_timestamp,
            expected_entry_timestamp=expected_entry_timestamp,
            signal_context=dict(event),
        )
        or ""
    ).strip()
    if not signal_id:
        raise CandidateAdapterContractError("candidate_adapter_contract_incomplete")
    return signal_id


def validate_candidate_binding(
    *,
    adapter: CandidateAdapter,
    preregistration: Mapping[str, Any],
    requested_candidate_id: str,
) -> None:
    """Fail closed unless all three candidate identities are identical."""

    frozen_candidate_id = str(preregistration.get("sourceCandidateId") or "")
    requested = str(requested_candidate_id or "")
    adapter_candidate_id = str(adapter.candidate_id or "")
    if not frozen_candidate_id or not requested or not adapter_candidate_id:
        raise CandidateAdapterIdentityError("candidate_id_missing")
    if len({frozen_candidate_id, requested, adapter_candidate_id}) != 1:
        raise CandidateAdapterIdentityError(
            "candidate_id_mismatch:"
            f"preregistration={frozen_candidate_id}:"
            f"requested={requested}:adapter={adapter_candidate_id}"
        )


def validate_formal_replay_event_indices(
    events: Sequence[Mapping[str, Any]],
) -> None:
    """Fail before fold assignment when an adapter omits index semantics."""

    required = ("signalIndex", "entryIndex", "exitIndex")
    for event_index, event in enumerate(events):
        for field in required:
            if field not in event or event[field] is None:
                raise CandidateAdapterContractError(
                    f"candidate_adapter_event_contract_missing:{field}:"
                    f"event={event_index}"
                )
        try:
            signal_index = int(event["signalIndex"])
            entry_index = int(event["entryIndex"])
            exit_index = int(event["exitIndex"])
        except (TypeError, ValueError) as error:
            raise CandidateAdapterContractError(
                f"candidate_adapter_event_index_invalid:event={event_index}"
            ) from error
        if signal_index < 0 or not signal_index <= entry_index <= exit_index:
            raise CandidateAdapterContractError(
                f"candidate_adapter_event_index_order_invalid:event={event_index}"
            )
