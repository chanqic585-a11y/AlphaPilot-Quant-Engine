from __future__ import annotations

from alphapilot.validation.risk_models import simulate_account_path


def _trade(
    instrument: str,
    entry: int,
    exit_: int,
    net_r: float,
    direction: str = "long",
) -> dict:
    return {
        "instrumentId": instrument,
        "entryTimestampMs": entry,
        "exitTimestampMs": exit_,
        "netR": net_r,
        "direction": direction,
    }


def test_primary_risk_model_enforces_open_risk_and_reports_path() -> None:
    model = {
        "riskPerTradePct": 0.25,
        "maximumOpenRiskPct": 0.5,
        "maximumConcurrentPositions": 2,
        "maximumSymbolRiskPct": 0.25,
        "maximumDirectionalClusterRiskPct": 0.5,
        "dailyNewRiskPausePct": -10.0,
        "drawdownResearchStopPct": 10.0,
    }
    trades = [
        _trade("BTC-USDT-SWAP", 1, 10, 2.0),
        _trade("ETH-USDT-SWAP", 2, 11, -1.0),
        _trade("SOL-USDT-SWAP", 3, 12, 2.0),
    ]

    report = simulate_account_path(trades, model=model, initial_equity=100.0)

    assert report["acceptedTradeCount"] == 2
    assert report["skippedTradeCount"] == 1
    assert report["maximumConcurrentPositions"] == 2
    assert report["maximumOpenRiskPct"] == 0.5
    assert report["finalEquity"] > 100.0
    assert report["leverageCanIncreaseAllowedLoss"] is False


def test_drawdown_stop_blocks_new_risk_without_changing_trade_results() -> None:
    model = {
        "riskPerTradePct": 1.0,
        "maximumOpenRiskPct": 1.0,
        "maximumConcurrentPositions": 1,
        "maximumSymbolRiskPct": 1.0,
        "maximumDirectionalClusterRiskPct": 1.0,
        "dailyNewRiskPausePct": -50.0,
        "drawdownResearchStopPct": 1.0,
    }
    trades = [
        _trade("BTC-USDT-SWAP", 1, 2, -2.0),
        _trade("ETH-USDT-SWAP", 3, 4, 3.0),
    ]

    report = simulate_account_path(trades, model=model, initial_equity=100.0)

    assert report["acceptedTradeCount"] == 1
    assert report["riskStopTriggerCount"] == 1
    assert report["skipReasons"]["drawdown_research_stop"] == 1
