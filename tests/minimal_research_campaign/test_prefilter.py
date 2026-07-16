from __future__ import annotations

from alphapilot.minimal_research_campaign.prefilter import (
    evaluate_event_prefilter,
    finalize_prefilter_route,
)


def _events(values: list[float]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, value in enumerate(values):
        rows.append(
            {
                "entryTimestamp": f"2024-{(index % 12) + 1:02d}-01T00:00:00+00:00",
                "symbol": f"C{index % 4}-USDT-SWAP",
                "grossR": value + 0.05,
                "costR": 0.05,
                "netR": value,
                "marketState": "bull" if index % 3 == 0 else "range",
                "volatilityState": "high" if index % 2 else "low",
            }
        )
    return rows


def test_event_prefilter_applies_frozen_structural_gates() -> None:
    result = evaluate_event_prefilter(
        _events([0.4] * 24 + [-0.2] * 12),
        gates={
            "minimumEvents": 30,
            "minimumProfitFactor": 1.03,
            "minimumAverageNetR": 0.0,
            "minimumTotalNetR": 0.0,
            "minimumPositiveMonthRatio": 0.5,
        },
    )

    assert result["eventCount"] == 36
    assert result["passed"] is True
    assert all(row["passed"] for row in result["gates"].values())
    assert set(result["regimeBreakdown"]) == {
        "marketState",
        "volatilityState",
    }


def test_failed_prefilter_is_archived_and_never_routes_to_formal_or_execution() -> None:
    failed = evaluate_event_prefilter(
        _events([-0.1] * 40),
        gates={
            "minimumEvents": 30,
            "minimumProfitFactor": 1.03,
            "minimumAverageNetR": 0.0,
            "minimumTotalNetR": 0.0,
            "minimumPositiveMonthRatio": 0.5,
        },
    )
    route = finalize_prefilter_route(
        [
            {
                "strategyId": "failed",
                "diagnosticOnly": False,
                "prefilter": failed,
            },
            {
                "strategyId": "diagnostic",
                "diagnosticOnly": True,
                "prefilter": {"passed": False},
            },
        ]
    )

    assert route["formalStrategyIds"] == []
    assert route["archivedStrategyIds"] == ["failed"]
    assert route["diagnosticStrategyIds"] == ["diagnostic"]
    assert route["formalStageAllowed"] is False
    assert route["demoReleaseCount"] == 0
    assert route["demoArm"] is False
    assert route["orderCount"] == 0

