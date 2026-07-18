from __future__ import annotations

from alphapilot.research_factory.program_v22 import (
    build_preflight_audit,
    build_formal_fold_boundaries,
    classify_v22_route,
    evaluate_economic_gates,
    materialize_capacity_rejection_evidence,
)


def test_five_frozen_formal_folds_cover_only_2023_and_2024() -> None:
    folds = build_formal_fold_boundaries(
        start="2023-01-01T00:00:00Z",
        end_exclusive="2025-01-01T00:00:00Z",
        fold_count=5,
        purge_bars=36,
        embargo_bars=36,
        timeframe="4h",
    )

    assert len(folds) == 5
    assert folds[0]["validationStart"] == "2023-01-01T00:00:00Z"
    assert folds[-1]["validationEnd"] == "2025-01-01T00:00:00Z"
    assert all(row["purgeBars"] == 36 for row in folds)
    assert all(row["embargoBars"] == 36 for row in folds)


def test_unknown_turnover_is_complete_stable_rejection_not_implementation_failure() -> None:
    event = {
        "signalId": "signal-1",
        "candidateId": "candidate-a",
        "symbol": "BTC-USDT-SWAP",
        "direction": "short",
        "signalTimestamp": "2024-01-01T00:00:00Z",
        "entryTimestamp": "2024-01-01T04:00:00Z",
        "entryPrice": 100.0,
        "initialStopPrice": 102.0,
        "foldId": "fold_01",
    }

    evidence = materialize_capacity_rejection_evidence(
        [event], capital_policy_hash="capital-hash", initial_capital=10000.0
    )

    assert evidence["coverage"]["eventDispositionPct"] == 100.0
    assert evidence["coverage"]["rankingEvidenceRecordPct"] == 100.0
    assert evidence["coverage"]["pitContextPct"] == 100.0
    assert evidence["coverage"]["capitalDecisionPct"] == 100.0
    assert evidence["coverage"]["positionSizePct"] == 100.0
    assert evidence["implementationBlockers"] == []
    assert evidence["capitalDecisions"][0]["reason"] == (
        "reject_capacity_evidence_unavailable"
    )


def test_zero_accepted_trades_routes_to_capital_infeasible_without_release() -> None:
    route = classify_v22_route(
        preflight_passed=True,
        accepted_trade_count=0,
        economic_gates_passed=False,
        statistical_gates_passed=False,
        funding_status="actual_available",
        clean_holdout_status="locked_unread",
    )

    assert route["status"] == "capital_infeasible"
    assert route["releaseEligible"] is False
    assert route["implementationValid"] is True


def test_preflight_requires_all_nine_formal_evidence_contracts() -> None:
    audit = build_preflight_audit(
        structural_certified=True,
        runtime_loaded=True,
        canonical_identity_pct=100.0,
        event_disposition_pct=100.0,
        ranking_evidence_pct=100.0,
        pit_context_pct=100.0,
        capital_decision_pct=100.0,
        position_size_pct=100.0,
        exit_fixture_passed=True,
    )

    assert audit["passed"] is True
    assert audit["passedCheckCount"] == 9
    assert audit["failedChecks"] == []


def test_zero_trade_fold_metrics_fail_economic_gate_without_implementation_failure() -> None:
    folds = [
        {
            "foldId": f"fold_{index:02d}",
            "tradeCount": 0,
            "profitFactor": None,
            "averageNetR": None,
            "totalNetR": 0.0,
            "maximumDrawdownPct": 0.0,
            "benchmarkIncrement": 0.0,
            "stress1_5xProfitFactor": None,
            "stress1_5xAverageNetR": None,
            "stress1_5xTotalNetR": 0.0,
        }
        for index in range(1, 6)
    ]
    gate = evaluate_economic_gates(
        fold_metrics=folds,
        minimum_profit_factor=1.05,
        maximum_drawdown_pct=15.0,
        minimum_positive_fold_count=3,
    )

    assert gate["completeFoldCount"] == 5
    assert gate["passed"] is False
    assert "minimumFormalEvents" in gate["failedGates"]
    assert gate["implementationBlockers"] == []
