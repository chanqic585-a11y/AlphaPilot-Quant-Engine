from __future__ import annotations

import pytest

from alphapilot.research_screening.event_strategy_gates import evaluate_event_strategy_gates


def _event_metrics(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "metricType": "event",
        "profitFactor": 1.20,
        "averageNetR": 0.08,
        "totalNetR": 8.0,
        "maximumDrawdownPct": 12.0,
        "positiveFoldCount": 4,
        "foldCount": 5,
        "eventCount": 320,
        "positiveMonthRatio": 0.70,
        "mfeMaeComplete": True,
        "simpleBenchmarkComplete": True,
    }
    payload.update(overrides)
    return payload


def test_event_formal_gate_uses_separate_walk_forward_and_holdout_metrics() -> None:
    result = evaluate_event_strategy_gates(
        timeframe="1h",
        development_metrics=_event_metrics(),
        walk_forward_metrics=_event_metrics(),
        holdout_metrics=_event_metrics(eventCount=110, profitFactor=1.05),
        stress_1_5x_metrics=_event_metrics(profitFactor=1.08, averageNetR=0.02),
        uncertainty={"profitFactorLower90": 1.01, "averageNetRLower90": 0.01},
        simple_benchmark_passed=True,
        capital_competition_passed=True,
        implementation_parity_passed=True,
        formal_data_provenance_passed=True,
    )

    assert result["developmentPrefilterPassed"] is True
    assert result["walkForwardNumericPassed"] is True
    assert result["cleanHoldoutPassed"] is True
    assert result["overallFormalPassed"] is True
    assert result["walkForwardMetrics"]["eventCount"] == 320
    assert result["holdoutMetrics"]["eventCount"] == 110


def test_event_gate_fails_closed_when_holdout_evidence_is_missing() -> None:
    result = evaluate_event_strategy_gates(
        timeframe="1h",
        development_metrics=_event_metrics(),
        walk_forward_metrics=_event_metrics(),
        holdout_metrics=None,
        stress_1_5x_metrics=_event_metrics(),
        uncertainty={"profitFactorLower90": 1.01, "averageNetRLower90": 0.01},
        simple_benchmark_passed=True,
        capital_competition_passed=True,
        implementation_parity_passed=True,
        formal_data_provenance_passed=True,
    )

    assert result["cleanHoldoutPassed"] is False
    assert result["overallFormalPassed"] is False
    assert "holdoutMetrics" in result["missingEvidence"]


def test_event_gate_rejects_portfolio_metric_contract() -> None:
    with pytest.raises(TypeError, match="event metrics"):
        evaluate_event_strategy_gates(
            timeframe="1h",
            development_metrics={"metricType": "portfolio"},
            walk_forward_metrics=_event_metrics(),
            holdout_metrics=_event_metrics(),
            stress_1_5x_metrics=_event_metrics(),
            uncertainty={"profitFactorLower90": 1.01, "averageNetRLower90": 0.01},
            simple_benchmark_passed=True,
            capital_competition_passed=True,
            implementation_parity_passed=True,
            formal_data_provenance_passed=True,
        )
