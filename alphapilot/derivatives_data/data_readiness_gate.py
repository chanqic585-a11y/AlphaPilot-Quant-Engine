"""Locked V13.27.1.12 direction and top-level family readiness gates."""

from __future__ import annotations

from typing import Any


def _passed(metrics: dict[str, Any], requirements: list[tuple[str, Any]]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    for field, expected in requirements:
        value = metrics.get(field)
        passed = expected(value) if callable(expected) else value == expected
        if not passed:
            blockers.append(field)
    return not blockers, blockers


def evaluate_family_readiness(evidence: dict[str, dict[str, Any]]) -> dict[str, Any]:
    a1 = evidence.get("A1", {})
    a1_passed, a1_blockers = _passed(
        a1,
        [
            (
                "liquidationStatus",
                lambda value: value
                in {"real_liquidation", "independently_validated_liquidation"},
            ),
            ("coveragePassed", True),
            ("qualityPassed", True),
        ],
    )
    a2 = evidence.get("A2", {})
    a2_ready = bool(a2.get("proxyCoveragePassed"))

    b = evidence.get("B", {})
    b_passed, b_blockers = _passed(
        b,
        [
            ("historyMonths", lambda value: (value or 0) >= 24),
            ("eligibleContracts", lambda value: (value or 0) >= 20),
            ("coreCoverage", lambda value: (value or 0) >= 0.95),
            (
                "maximumInstrumentMissingRate",
                lambda value: value is not None and value <= 0.02,
            ),
            ("unexplainedLongGapCount", 0),
            ("futureLeakCount", 0),
            ("sameExchangeCoreChain", True),
            ("qualityPassed", True),
        ],
    )

    c = evidence.get("C", {})
    c_passed, c_blockers = _passed(
        c,
        [
            ("historyMonths", lambda value: (value or 0) >= 24),
            ("pitSnapshotCoverage", lambda value: (value or 0) >= 0.95),
            ("medianInvestableContracts", lambda value: (value or 0) >= 30),
            ("majorityDatesAtLeast30", True),
            ("researchSymbolCount", lambda value: (value or 0) >= 8),
            ("holdoutSymbolCount", lambda value: (value or 0) >= 8),
            ("currentTopNBackfill", False),
            ("qualityPassed", True),
        ],
    )
    directions = {
        "A1": {"status": "formal_ready" if a1_passed else "unavailable", "blockers": a1_blockers},
        "A2": {
            "status": "provisional_ready" if a2_ready else "unavailable",
            "blockers": [] if a2_ready else ["proxyCoveragePassed"],
        },
        "B": {"status": "formal_ready" if b_passed else "provisional_ready" if b else "unavailable", "blockers": b_blockers},
        "C": {"status": "formal_ready" if c_passed else "provisional_ready" if c else "unavailable", "blockers": c_blockers},
    }
    families = {
        "stress_reversal": {
            "status": (
                "formal_ready"
                if a1_passed or b_passed
                else "provisional_ready"
                if a2_ready or bool(b)
                else "unavailable"
            ),
            "formalDirections": [name for name, passed in (("A1", a1_passed), ("B", b_passed)) if passed],
        },
        "cross_sectional_momentum": {
            "status": "formal_ready" if c_passed else "provisional_ready" if c else "unavailable",
            "formalDirections": ["C"] if c_passed else [],
        },
    }
    formal_count = sum(1 for row in families.values() if row["status"] == "formal_ready")
    status = "data_ready" if formal_count >= 2 else "partial_data_ready" if formal_count == 1 else "data_not_ready"
    campaign_may_run = formal_count >= 2 and c_passed
    return {
        "status": status,
        "directions": directions,
        "topLevelFamilies": families,
        "formalTopLevelFamilyCount": formal_count,
        "qlibCampaignMayRun": campaign_may_run,
        "threeDirectionCampaignMayRun": campaign_may_run,
        "provisionalCountedAsFormal": False,
    }
