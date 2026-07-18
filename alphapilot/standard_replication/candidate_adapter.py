"""Candidate-neutral identity adapter for registered replication plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.formal_validation.candidate_adapter import (
    CandidateAdapterContractError,
    CandidateAdapterIdentityError,
)

from .registry import ReplicationFamily, ReplicationVariant


class CanonicalReplicationCandidateAdapter:
    """Freezes identity now while execution remains fail-closed until V36."""

    adapter_version = "v35.0"

    def __init__(
        self,
        *,
        family: ReplicationFamily,
        variant: ReplicationVariant,
    ) -> None:
        if variant not in family.variants:
            raise CandidateAdapterIdentityError("variant_not_registered_for_family")
        self.family = family
        self.variant = variant
        self.candidate_id = variant.candidate_id
        self.adapter_id = f"canonical_replication:{family.family_id}"

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
        if str(candidate_id) != self.candidate_id:
            raise CandidateAdapterIdentityError("candidate_id_mismatch")
        identity = {
            "candidateId": self.candidate_id,
            "familyId": self.family.family_id,
            "symbol": str(symbol),
            "direction": str(direction),
            "signalTimestamp": str(signal_timestamp),
            "expectedEntryTimestamp": expected_entry_timestamp,
            "signalContext": dict(signal_context),
        }
        return stable_hash(identity, prefix="replication_signal")

    def resolve_candidate(
        self,
        *,
        repo_root: Path,
        preregistration: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        frozen_candidate_id = str(preregistration.get("sourceCandidateId") or "")
        if frozen_candidate_id != self.candidate_id:
            raise CandidateAdapterIdentityError("candidate_id_mismatch")
        return {
            "candidateId": self.candidate_id,
            "familyId": self.family.family_id,
            "adapterId": self.adapter_id,
            "adapterVersion": self.adapter_version,
            "adaptation": self.variant.adaptation,
            "definitionPath": self.variant.definition_path,
            "repoRoot": str(Path(repo_root).resolve()),
        }

    def replay(
        self,
        *,
        candidate: Mapping[str, Any],
        frames: Mapping[str, pd.DataFrame],
        round_trip_cost_rate: float,
    ) -> Sequence[Mapping[str, Any]]:
        raise CandidateAdapterContractError(
            "replication_not_executable_until_v36"
        )

    def run_parity(
        self,
        *,
        bundle: object,
        repo_root: Path,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        raise CandidateAdapterContractError(
            "replication_not_executable_until_v36"
        )
