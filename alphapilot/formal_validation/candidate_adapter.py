"""Candidate-neutral contract for formal validation engines."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

import pandas as pd


class CandidateAdapterIdentityError(ValueError):
    """Raised when CLI, preregistration, and adapter identities diverge."""


@runtime_checkable
class CandidateAdapter(Protocol):
    """Boundary between a candidate implementation and the formal core."""

    candidate_id: str
    adapter_id: str
    adapter_version: str

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
