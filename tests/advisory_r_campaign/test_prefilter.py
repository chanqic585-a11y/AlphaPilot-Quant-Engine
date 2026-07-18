from alphapilot.advisory_r_campaign.prefilter import (
    evaluate_candidate,
    route_prefilter_survivors,
)


def _result(
    candidate_id: str,
    family_id: str,
    *,
    passed: bool,
    complexity: int = 3,
    drawdown: float = 0.2,
    turnover: float = 1.0,
    benchmark_increment: float = 0.1,
    diagnostic_only: bool = False,
) -> dict:
    return {
        "candidateId": candidate_id,
        "familyId": family_id,
        "passed": passed,
        "complexityScore": complexity,
        "maximumDrawdown": drawdown,
        "turnover": turnover,
        "simpleBenchmarkIncrement": benchmark_increment,
        "diagnosticOnly": diagnostic_only,
    }


def test_target_r_is_advisory_and_not_a_prefilter_gate() -> None:
    events = [
        {
            "entryTimestamp": f"2026-{month:02d}-01T00:00:00+00:00",
            "netR": 0.25,
            "grossR": 0.30,
            "costR": 0.05,
        }
        for month in range(1, 9)
    ]
    candidate = {
        "candidateId": "advisory_target",
        "familyId": "session",
        "diagnosticOnly": False,
        "strategyType": "event",
        "exitPolicy": {"mode": "fixed_r", "parameters": {"targetR": 1.2}},
    }

    result = evaluate_candidate(
        candidate,
        events,
        gates={
            "minimumEvents": 8,
            "minimumProfitFactor": 1.03,
            "minimumAverageNetR": 0.0,
            "minimumTotalNetR": 0.0,
            "minimumPositiveMonthRatio": 0.5,
            "maximumDrawdown": 0.35,
        },
    )

    assert result["passed"] is True
    assert "minimumTargetR" not in result["gates"]
    assert result["targetRAdvisory"] == 1.2


def test_router_caps_six_and_one_candidate_per_family() -> None:
    results = [
        _result("a1", "family_a", passed=True, complexity=4),
        _result("a2", "family_a", passed=True, complexity=2),
        _result("b", "family_b", passed=True),
        _result("c", "family_c", passed=True),
        _result("d", "family_d", passed=True),
        _result("e", "family_e", passed=True),
        _result("f", "family_f", passed=True),
        _result("g", "family_g", passed=True),
        _result("diagnostic", "family_h", passed=True, diagnostic_only=True),
    ]

    route = route_prefilter_survivors(results, maximum_survivors=6)

    assert len(route["formalCandidateIds"]) == 6
    assert "a2" in route["formalCandidateIds"]
    assert "a1" not in route["formalCandidateIds"]
    selected = [row for row in results if row["candidateId"] in route["formalCandidateIds"]]
    assert len({row["familyId"] for row in selected}) == len(selected)
    assert route["diagnosticCandidateIds"] == ["diagnostic"]


def test_zero_survivors_is_a_valid_hard_stop() -> None:
    route = route_prefilter_survivors(
        [_result("failed", "family", passed=False)],
        maximum_survivors=6,
    )

    assert route["formalCandidateIds"] == []
    assert route["formalStageAllowed"] is False
    assert route["hardStopReason"] == "zero_prefilter_survivors"
    assert route["demoReleaseCount"] == 0
