from __future__ import annotations

from alphapilot.validation.portfolio_risk import analyze_portfolio_risk


def test_portfolio_risk_reports_overlap_and_preregistered_limits() -> None:
    reports = {
        "a": [
            {"instrumentId": "BTC-USDT-SWAP", "entryTimestampMs": 1, "netR": 1.0},
            {"instrumentId": "ETH-USDT-SWAP", "entryTimestampMs": 2, "netR": -0.5},
        ],
        "b": [
            {"instrumentId": "BTC-USDT-SWAP", "entryTimestampMs": 1, "netR": 0.5},
            {"instrumentId": "SOL-USDT-SWAP", "entryTimestampMs": 3, "netR": 1.0},
        ],
    }

    result = analyze_portfolio_risk(reports)

    assert result["portfolioLimits"]["maximumCandidateFamilies"] == 2
    assert result["portfolioLimits"]["maximumAggregateOpenRiskPct"] == 1.25
    assert result["signalOverlapJaccard"]["a"]["b"] == 1 / 3
    assert result["btcBeta"] is None
