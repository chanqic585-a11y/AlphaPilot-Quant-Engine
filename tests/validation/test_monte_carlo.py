from __future__ import annotations

from alphapilot.validation.monte_carlo import run_monte_carlo


def test_monte_carlo_is_seeded_and_reports_tail_risk() -> None:
    values = [2.0, -1.0, 0.5, -0.5, 1.0] * 8

    first = run_monte_carlo(values, risk_per_trade_pct=0.25, draws=250, seed=41)
    second = run_monte_carlo(values, risk_per_trade_pct=0.25, draws=250, seed=41)

    assert first == second
    assert first["draws"] == 250
    assert first["maximumDrawdownPct"]["median"] >= 0
    assert first["maximumDrawdownPct"]["p95"] >= first["maximumDrawdownPct"]["median"]
    assert 0 <= first["probabilityDrawdownAtLeast10Pct"] <= 1
    assert 0 <= first["probabilityRuin"] <= 1


def test_monte_carlo_can_return_deterministic_raw_sample_rows() -> None:
    first = run_monte_carlo(
        [1.0, -0.5, 0.25],
        risk_per_trade_pct=0.25,
        draws=7,
        seed=123,
        include_sample_rows=True,
    )
    second = run_monte_carlo(
        [1.0, -0.5, 0.25],
        risk_per_trade_pct=0.25,
        draws=7,
        seed=123,
        include_sample_rows=True,
    )

    assert first["sampleRows"] == second["sampleRows"]
    assert len(first["sampleRows"]) == 7
    assert first["sampleRows"][0]["drawIndex"] == 0
    assert first["sampleRows"][0]["ruined"] is False
