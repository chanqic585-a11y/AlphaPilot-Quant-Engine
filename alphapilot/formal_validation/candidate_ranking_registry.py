"""Immutable registry for candidate-owned ranking contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash

from .candidate_ranking_contract import validate_candidate_ranking_contract


class CandidateRankingRegistryError(ValueError):
    """Raised when registry identity or immutability rules are violated."""


class CandidateRankingRegistry:
    def __init__(self) -> None:
        self._contracts: dict[str, dict[str, Any]] = {}

    def register(self, contract: Mapping[str, Any]) -> dict[str, Any]:
        validation = validate_candidate_ranking_contract(contract)
        candidate_id = validation["candidateId"]
        canonical = dict(contract)
        canonical["contractHash"] = validation["contractHash"]
        canonical["candidateRankingContractId"] = validation["contractHash"]
        existing = self._contracts.get(candidate_id)
        if existing and existing["contractHash"] != canonical["contractHash"]:
            raise CandidateRankingRegistryError(
                f"conflicting_candidate_contract:{candidate_id}"
            )
        self._contracts[candidate_id] = canonical
        return dict(canonical)

    def resolve(self, candidate_id: str) -> dict[str, Any]:
        try:
            return dict(self._contracts[str(candidate_id)])
        except KeyError as exc:
            raise CandidateRankingRegistryError(
                f"candidate_contract_not_registered:{candidate_id}"
            ) from exc

    def manifest(self) -> dict[str, Any]:
        candidate_ids = sorted(self._contracts)
        contracts = [dict(self._contracts[candidate_id]) for candidate_id in candidate_ids]
        payload: dict[str, Any] = {
            "schemaVersion": "candidate_ranking_registry_v1",
            "candidateCount": len(candidate_ids),
            "candidateIds": candidate_ids,
            "contracts": contracts,
        }
        payload["registryHash"] = stable_hash(
            payload, prefix="candidate_ranking_registry"
        )
        return payload


__all__ = ["CandidateRankingRegistry", "CandidateRankingRegistryError"]
