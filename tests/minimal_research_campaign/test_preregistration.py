from __future__ import annotations

import json

import pytest

from alphapilot.minimal_research_campaign.preregistration import (
    build_formal_preregistration,
    build_prefilter_preregistration,
)


def _members() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index in range(12):
        symbol = f"C{index:02d}-USDT-SWAP"
        if index == 0:
            symbol = "BTC-USDT-SWAP"
        elif index == 1:
            symbol = "ETH-USDT-SWAP"
        rows.append(
            {
                "instrumentId": symbol,
                "historyMonths": 48 + index,
                "liquidityScore": 100 - index,
                "volatilityScore": index / 10,
                "profiles": {
                    "4h": {
                        "effectiveBacktestStart": "2020-01-01T00:00:00+00:00"
                    }
                },
            }
        )
    return rows


def test_prefilter_preregistration_freezes_bounded_inventory_and_nonzero_costs() -> None:
    preregistration = build_prefilter_preregistration(
        core_universe={
            "coreUniverseHash": "core-hash",
            "commonCutoffByTimeframe": {"4h": "2026-01-01T00:00:00+00:00"},
            "members": _members(),
        },
        snapshot={"snapshotId": "snapshot-id", "snapshotHash": "snapshot-hash"},
        archived_family_ids={"trend_pullback", "breakout"},
        implementation_commit="abc123",
        implementation_source_hashes={"campaign_runner.py": "source-hash"},
    )

    assert len(preregistration["hypotheses"]) == 3
    assert 8 <= len(preregistration["representativeUniverse"]) <= 12
    assert preregistration["costModel"]["roundTripRate"] > 0
    assert preregistration["eventExecution"]["remainingTargetR"] >= 2
    assert preregistration["eventExecution"]["nextBarOnly"] is True
    assert preregistration["eventExecution"]["initialStopMayWiden"] is False
    assert preregistration["dataBoundary"]["developmentFraction"] == 0.55
    assert preregistration["experimentBudget"]["maximumHypotheses"] == 3
    assert preregistration["experimentBudget"]["prefilterRevisionsPerFamily"] == 0
    assert preregistration["safetyBoundary"] == {
        "demoArm": False,
        "demoReleaseCount": 0,
        "orderCount": 0,
        "liveTradingEnabled": False,
        "withdrawEnabled": False,
    }
    serialized = json.dumps(preregistration).lower()
    assert "api key" not in serialized
    assert "createorder" not in serialized


def test_formal_preregistration_accepts_only_prefilter_survivors() -> None:
    prefilter = build_prefilter_preregistration(
        core_universe={
            "coreUniverseHash": "core-hash",
            "commonCutoffByTimeframe": {"4h": "2026-01-01T00:00:00+00:00"},
            "members": _members(),
        },
        snapshot={"snapshotId": "snapshot-id", "snapshotHash": "snapshot-hash"},
        archived_family_ids={"trend_pullback", "breakout"},
        implementation_commit="abc123",
        implementation_source_hashes={"campaign_runner.py": "source-hash"},
    )

    with pytest.raises(ValueError, match="survivor"):
        build_formal_preregistration(prefilter, survivor_strategy_ids=[])

    formal = build_formal_preregistration(
        prefilter,
        survivor_strategy_ids=["core_idiosyncratic_selloff_recovery_long_4h"],
    )
    assert formal["strategyIds"] == [
        "core_idiosyncratic_selloff_recovery_long_4h"
    ]
    assert formal["partitions"] == {
        "development": 0.55,
        "purgedWalkForward": 0.25,
        "campaignLockedOos": 0.20,
    }
    assert formal["walkForward"]["foldCount"] == 5
    assert formal["campaignLockedOos"]["maximumUnlockCount"] == 1
    assert formal["safetyBoundary"]["demoArm"] is False

