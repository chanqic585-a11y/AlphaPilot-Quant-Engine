from alphapilot.research_screening.campaign_metrics import (
    evaluate_candidate_gates,
    selection_events,
    summarize_events,
)


def _event(net_r: float, *, split: str, fold: str, symbol: str, month: str) -> dict:
    return {
        "netR": net_r,
        "grossR": net_r + 0.1,
        "feesR": 0.04,
        "slippageR": 0.03,
        "fundingR": 0.01,
        "spreadProxyR": 0.02,
        "split": split,
        "foldId": fold,
        "symbol": symbol,
        "entryTimestamp": f"{month}-10T00:00:00+00:00",
    }


def test_selection_events_never_expose_holdout() -> None:
    events = [
        _event(1.0, split="development", fold="", symbol="A", month="2024-01"),
        _event(1.0, split="walk_forward", fold="fold_001", symbol="B", month="2024-02"),
        _event(99.0, split="holdout", fold="", symbol="C", month="2024-03"),
    ]
    selected = selection_events(events)

    assert len(selected) == 2
    assert all(event["split"] != "holdout" for event in selected)


def test_summary_reports_profit_drawdown_and_concentration() -> None:
    events = [
        _event(2.0, split="walk_forward", fold="fold_001", symbol="A", month="2024-01"),
        _event(-1.0, split="walk_forward", fold="fold_002", symbol="B", month="2024-02"),
        _event(1.0, split="walk_forward", fold="fold_003", symbol="B", month="2024-03"),
    ]
    summary = summarize_events(events)

    assert summary["profitFactor"] == 3.0
    assert summary["averageNetR"] == 2 / 3
    assert summary["totalNetR"] == 2.0
    assert summary["maximumDrawdownPct"] == 1.0
    assert 0 <= summary["singleInstrumentPositiveContribution"] <= 1


def test_gate_rows_are_hashed_and_do_not_force_a_pass() -> None:
    events = [
        _event(-1.0, split="development", fold="", symbol="A", month="2024-01"),
        _event(-1.0, split="walk_forward", fold="fold_001", symbol="A", month="2024-02"),
        _event(2.0, split="holdout", fold="", symbol="B", month="2024-03"),
    ]
    preregistration = {
        "sampleGates": {"1h": {"minimumEvents": 1, "minimumMonths": 1}},
        "prescreenGates": {
            "developmentProfitFactor": {"operator": ">=", "required": 1.08},
            "developmentAverageNetR": {"operator": ">=", "required": 0.03},
            "positiveDevelopmentMonthRatio": {"operator": ">=", "required": 0.6},
        },
        "baseGates": {
            "oosProfitFactor": {"operator": ">=", "required": 1.05},
            "oosAverageNetR": {"operator": ">", "required": 0.0},
            "oosTotalNetR": {"operator": ">", "required": 0.0},
            "maximumDrawdownPct": {"operator": "<=", "required": 25.0},
            "positiveFoldCount": {"operator": ">=", "required": 3},
        },
        "formalGates": {
            "oosProfitFactor": {"operator": ">=", "required": 1.15},
            "oosAverageNetR": {"operator": ">=", "required": 0.05},
            "oosTotalNetR": {"operator": ">", "required": 0.0},
            "maximumDrawdownPct": {"operator": "<=", "required": 20.0},
            "positiveFoldCount": {"operator": ">=", "required": 4},
            "stress1_5xProfitFactor": {"operator": ">=", "required": 1.05},
            "stress1_5xAverageNetR": {"operator": ">", "required": 0.0},
            "singleInstrumentPositiveContribution": {"operator": "<=", "required": 0.35},
            "singleMonthPositiveContribution": {"operator": "<=", "required": 0.35},
            "holdoutAccessBeforeFinalEvaluation": {"operator": "==", "required": 0},
        },
    }
    result = evaluate_candidate_gates(
        events=events,
        timeframe="1h",
        preregistration=preregistration,
        holdout_access_before_final_evaluation=0,
    )

    assert result["prescreenPassed"] is False
    assert result["formalPassed"] is False
    assert result["formalGates"]["oosProfitFactor"]["evidenceHash"].startswith("gate_evidence_")
