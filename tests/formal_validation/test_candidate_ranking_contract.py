from __future__ import annotations

import inspect

import pytest

from alphapilot.formal_validation import candidate_ranking_contract as module
from alphapilot.formal_validation.candidate_ranking_contract import (
    CandidateRankingContractError,
    build_candidate_ranking_contract,
    validate_candidate_ranking_contract,
)


def _slot(*, order: str) -> dict[str, object]:
    return {
        "semanticDefinition": "closed-bar event magnitude",
        "sourceVariables": ["close", "atr14"],
        "formula": "abs(close - reference) / atr14",
        "normalization": "atr14",
        "lookback": 14,
        "order": order,
        "availableAt": "signal_close",
        "pointInTimeRule": "uses bars at or before signal close",
        "missingPolicy": "reject_signal",
    }


def test_contract_is_candidate_neutral_canonical_and_stable() -> None:
    contract = build_candidate_ranking_contract(
        candidate_id="fixture-directional-a",
        family_id="fixture-family-a",
        primary_event_severity=_slot(order="descending"),
        confirmation_strength=_slot(order="descending"),
        liquidity_30d={
            "dataProfileHash": "profile-hash",
            "formula": "sum(quote_turnover for prior 30 completed UTC days)",
            "lookback": "30_completed_utc_days",
            "order": "descending",
            "availableAt": "signal_close",
            "missingPolicy": "reject_signal",
        },
        instrument_id={"order": "ascending", "exactCanonicalIdentity": True},
    )

    assert contract["schemaVersion"] == "candidate_ranking_contract_v1"
    assert contract["candidateRankingContractId"].startswith(
        "candidate_ranking_contract_"
    )
    assert validate_candidate_ranking_contract(contract)["status"] == "valid"
    assert build_candidate_ranking_contract(
        candidate_id="fixture-directional-a",
        family_id="fixture-family-a",
        primary_event_severity=_slot(order="descending"),
        confirmation_strength=_slot(order="descending"),
        liquidity_30d={
            "dataProfileHash": "profile-hash",
            "formula": "sum(quote_turnover for prior 30 completed UTC days)",
            "lookback": "30_completed_utc_days",
            "order": "descending",
            "availableAt": "signal_close",
            "missingPolicy": "reject_signal",
        },
        instrument_id={"order": "ascending", "exactCanonicalIdentity": True},
    )["contractHash"] == contract["contractHash"]

    source = inspect.getsource(module)
    for forbidden in ("eventExtremeResidualZ", "recoverySizeZ", "Trend Failure"):
        assert forbidden not in source


def test_contract_rejects_incomplete_semantics() -> None:
    broken = _slot(order="descending")
    broken.pop("lookback")
    with pytest.raises(CandidateRankingContractError, match="lookback"):
        build_candidate_ranking_contract(
            candidate_id="fixture-directional-a",
            family_id="fixture-family-a",
            primary_event_severity=broken,
            confirmation_strength=_slot(order="descending"),
            liquidity_30d={
                "dataProfileHash": "profile-hash",
                "formula": "prior completed turnover",
                "lookback": 30,
                "order": "descending",
                "availableAt": "signal_close",
                "missingPolicy": "reject_signal",
            },
            instrument_id={"order": "ascending", "exactCanonicalIdentity": True},
        )
