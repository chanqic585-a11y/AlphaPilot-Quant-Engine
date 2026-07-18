"""Candidate-neutral semantic contract for point-in-time signal ranking."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


class CandidateRankingContractError(ValueError):
    """Raised when a candidate ranking contract is incomplete or unsafe."""


_SEMANTIC_SLOT_FIELDS = (
    "semanticDefinition",
    "sourceVariables",
    "formula",
    "normalization",
    "lookback",
    "order",
    "availableAt",
    "pointInTimeRule",
    "missingPolicy",
)
_LIQUIDITY_FIELDS = (
    "dataProfileHash",
    "formula",
    "lookback",
    "order",
    "availableAt",
    "missingPolicy",
)
_VALID_ORDERS = {"ascending", "descending"}


def _mapping(value: Mapping[str, Any], *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CandidateRankingContractError(f"{name}:mapping_required")
    return dict(value)


def _require_fields(value: Mapping[str, Any], fields: tuple[str, ...], *, name: str) -> None:
    missing = [field for field in fields if value.get(field) in (None, "", [])]
    if missing:
        raise CandidateRankingContractError(f"{name}:missing:{','.join(missing)}")
    if value.get("order") not in _VALID_ORDERS:
        raise CandidateRankingContractError(f"{name}:invalid_order")


def validate_candidate_ranking_contract(
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    candidate_id = str(contract.get("candidateId") or "").strip()
    family_id = str(contract.get("familyId") or "").strip()
    if not candidate_id or not family_id:
        raise CandidateRankingContractError("candidate_or_family_identity_missing")
    primary = _mapping(contract.get("primaryEventSeverity") or {}, name="primaryEventSeverity")
    confirmation = _mapping(
        contract.get("confirmationStrength") or {}, name="confirmationStrength"
    )
    liquidity = _mapping(contract.get("liquidity30d") or {}, name="liquidity30d")
    instrument = _mapping(contract.get("instrumentId") or {}, name="instrumentId")
    _require_fields(primary, _SEMANTIC_SLOT_FIELDS, name="primaryEventSeverity")
    _require_fields(
        confirmation, _SEMANTIC_SLOT_FIELDS, name="confirmationStrength"
    )
    _require_fields(liquidity, _LIQUIDITY_FIELDS, name="liquidity30d")
    if instrument.get("order") != "ascending":
        raise CandidateRankingContractError("instrumentId:order_must_be_ascending")
    if instrument.get("exactCanonicalIdentity") is not True:
        raise CandidateRankingContractError(
            "instrumentId:exact_canonical_identity_required"
        )
    expected_hash = stable_hash(
        {
            key: value
            for key, value in dict(contract).items()
            if key not in {"contractHash", "candidateRankingContractId"}
        },
        prefix="candidate_ranking_contract",
    )
    supplied_hash = contract.get("contractHash")
    if supplied_hash not in (None, expected_hash):
        raise CandidateRankingContractError("contract_hash_mismatch")
    return {
        "schemaVersion": "candidate_ranking_contract_validation_v1",
        "status": "valid",
        "candidateId": candidate_id,
        "familyId": family_id,
        "contractHash": expected_hash,
    }


def build_candidate_ranking_contract(
    *,
    candidate_id: str,
    family_id: str,
    primary_event_severity: Mapping[str, Any],
    confirmation_strength: Mapping[str, Any],
    liquidity_30d: Mapping[str, Any],
    instrument_id: Mapping[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": "candidate_ranking_contract_v1",
        "candidateId": str(candidate_id),
        "familyId": str(family_id),
        "primaryEventSeverity": dict(primary_event_severity),
        "confirmationStrength": dict(confirmation_strength),
        "liquidity30d": dict(liquidity_30d),
        "instrumentId": dict(instrument_id),
        "missingValuePolicy": "reject_signal",
        "postEntryDataPolicy": "forbidden",
        "economicResultReadPolicy": "forbidden",
    }
    validation = validate_candidate_ranking_contract(payload)
    payload["contractHash"] = validation["contractHash"]
    payload["candidateRankingContractId"] = validation["contractHash"]
    return payload


__all__ = [
    "CandidateRankingContractError",
    "build_candidate_ranking_contract",
    "validate_candidate_ranking_contract",
]
