from __future__ import annotations

from alphapilot.validation.candidate_selection import discover_candidates


def _row(
    strategy_id: str,
    family: str,
    *,
    timeframe: str = "1h",
    primary: str = "risk_model_failure",
    profit_factor: float | None = 1.2,
    average_net_r: float | None = 0.1,
) -> dict:
    return {
        "strategyId": strategy_id,
        "strategyName": family,
        "strategyFamily": family,
        "timeframe": timeframe,
        "status": "archived",
        "primaryFailureType": primary,
        "signalLayer": {
            "profitFactor": profit_factor,
            "averageNetR": average_net_r,
        },
        "evidenceBasis": {"tradeCount": 100},
    }


def test_discovers_only_risk_model_failure_candidates() -> None:
    rows = [
        _row("v1", "event_1d_breakout_retest_atr20_v1", timeframe="1d"),
        _row("v2", "negative_edge", primary="signal_edge_failure"),
    ]

    candidates = discover_candidates(rows)

    assert [candidate.strategy_version_id for candidate in candidates] == ["v1"]
    assert candidates[0].tier == "A"
    assert candidates[0].display_label_zh == "1D 趋势突破回踩 ATR2.0"


def test_c_tier_is_marked_for_prefilter() -> None:
    rows = [
        _row(
            "v-c",
            "short_cycle_event_15m_failed_breakout_factor_v2",
            timeframe="15m",
            profit_factor=1.009,
            average_net_r=0.006,
        )
    ]

    candidate = discover_candidates(rows)[0]

    assert candidate.tier == "C"
    assert candidate.requires_prefilter is True
    assert candidate.historical_prefilter_passed is False


def test_missing_metrics_stay_none() -> None:
    candidate = discover_candidates(
        [
            _row(
                "v-missing",
                "event_1d_oversold_sweep_reclaim_atr12_v1",
                timeframe="1d",
                profit_factor=None,
                average_net_r=None,
            )
        ]
    )[0]

    assert candidate.historical_profit_factor is None
    assert candidate.historical_average_net_r is None
    assert candidate.historical_prefilter_passed is False

