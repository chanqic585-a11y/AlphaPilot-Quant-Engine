from __future__ import annotations

import pytest

from alphapilot.formal_validation.candidate_ranking_contract import (
    build_candidate_ranking_contract,
)
from alphapilot.formal_validation.candidate_ranking_registry import (
    CandidateRankingRegistry,
    CandidateRankingRegistryError,
)


def _contract(candidate_id: str, family_id: str) -> dict[str, object]:
    slot = {
        "semanticDefinition": "fixture event magnitude",
        "sourceVariables": ["close"],
        "formula": "abs(close)",
        "normalization": "none",
        "lookback": 1,
        "order": "descending",
        "availableAt": "signal_close",
        "pointInTimeRule": "closed bar only",
        "missingPolicy": "reject_signal",
    }
    return build_candidate_ranking_contract(
        candidate_id=candidate_id,
        family_id=family_id,
        primary_event_severity=slot,
        confirmation_strength=slot,
        liquidity_30d={
            "dataProfileHash": "profile-hash",
            "formula": "prior turnover",
            "lookback": 30,
            "order": "descending",
            "availableAt": "signal_close",
            "missingPolicy": "reject_signal",
        },
        instrument_id={"order": "ascending", "exactCanonicalIdentity": True},
    )


def test_registry_supports_two_independent_candidate_fixtures() -> None:
    registry = CandidateRankingRegistry()
    a = registry.register(_contract("synthetic-a", "family-a"))
    b = registry.register(_contract("synthetic-b", "family-b"))

    assert registry.resolve("synthetic-a")["contractHash"] == a["contractHash"]
    assert registry.resolve("synthetic-b")["contractHash"] == b["contractHash"]
    manifest = registry.manifest()
    assert manifest["candidateCount"] == 2
    assert manifest["candidateIds"] == ["synthetic-a", "synthetic-b"]


def test_registry_rejects_conflicting_redefinition() -> None:
    registry = CandidateRankingRegistry()
    registry.register(_contract("synthetic-a", "family-a"))
    with pytest.raises(CandidateRankingRegistryError, match="conflicting"):
        registry.register(_contract("synthetic-a", "different-family"))
