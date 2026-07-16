from __future__ import annotations

from alphapilot.derivatives_data.data_readiness_gate import evaluate_family_readiness


def test_b_and_c_formal_readiness_require_full_locked_thresholds() -> None:
    result = evaluate_family_readiness(
        {
            "A1": {"liquidationStatus": "unavailable"},
            "A2": {"proxyCoveragePassed": True},
            "B": {
                "historyMonths": 24,
                "eligibleContracts": 20,
                "coreCoverage": 0.95,
                "maximumInstrumentMissingRate": 0.02,
                "unexplainedLongGapCount": 0,
                "futureLeakCount": 0,
                "sameExchangeCoreChain": True,
                "qualityPassed": True,
            },
            "C": {
                "historyMonths": 24,
                "pitSnapshotCoverage": 0.95,
                "medianInvestableContracts": 30,
                "majorityDatesAtLeast30": True,
                "researchSymbolCount": 8,
                "holdoutSymbolCount": 8,
                "currentTopNBackfill": False,
                "qualityPassed": True,
            },
        }
    )

    assert result["directions"]["A2"]["status"] == "provisional_ready"
    assert result["directions"]["B"]["status"] == "formal_ready"
    assert result["directions"]["C"]["status"] == "formal_ready"
    assert result["formalTopLevelFamilyCount"] == 2
    assert result["status"] == "data_ready"


def test_partial_or_provisional_directions_never_count_as_formal_families() -> None:
    result = evaluate_family_readiness(
        {
            "A1": {"liquidationStatus": "proxy_liquidation"},
            "A2": {"proxyCoveragePassed": True},
            "B": {"historyMonths": 12},
            "C": {"historyMonths": 24, "currentTopNBackfill": True},
        }
    )

    assert result["formalTopLevelFamilyCount"] == 0
    assert result["status"] == "data_not_ready"
    assert result["qlibCampaignMayRun"] is False
    assert result["threeDirectionCampaignMayRun"] is False
