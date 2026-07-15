from __future__ import annotations

from alphapilot.research_screening.formal_data_gate import evaluate_formal_data_gate


def test_proxy_liquidation_variant_is_permanently_provisional() -> None:
    result = evaluate_formal_data_gate(
        direction="A2",
        evidence={"oi": {"exchange": "OKX"}, "volumeWickProxy": True},
    )

    assert result["formalDataProvenancePassed"] is False
    assert result["maximumOutcome"] == "provisional_research_pass"
    assert "realLiquidation" in result["missingEvidence"]


def test_short_crowding_requires_same_exchange_core_fields() -> None:
    incomplete = evaluate_formal_data_gate(
        direction="B",
        evidence={
            "funding": {"exchange": "OKX"},
            "openInterest": {"exchange": "OKX"},
            "perpetualPrice": {"exchange": "OKX"},
            "spotPrice": {"exchange": "OKX"},
        },
    )
    complete = evaluate_formal_data_gate(
        direction="B",
        evidence={
            name: {"exchange": "OKX", "provenanceHash": f"hash-{name}"}
            for name in ("funding", "openInterest", "perpetualPrice", "spotPrice", "basis")
        },
    )

    assert incomplete["formalDataProvenancePassed"] is False
    assert "basis" in incomplete["missingEvidence"]
    assert complete["formalDataProvenancePassed"] is True


def test_cross_sectional_current_top_n_backfill_is_only_provisional() -> None:
    result = evaluate_formal_data_gate(
        direction="C",
        evidence={
            "pitTradability": True,
            "pitLiquidity": True,
            "listingDelisting": True,
            "historicalContractUniverse": True,
            "currentTopNBackfill": True,
        },
    )

    assert result["formalDataProvenancePassed"] is False
    assert result["maximumOutcome"] == "provisional_research_pass"
    assert "pointInTimeUniverseWithoutBackfill" in result["missingEvidence"]
