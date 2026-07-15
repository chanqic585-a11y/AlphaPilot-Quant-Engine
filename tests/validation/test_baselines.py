from __future__ import annotations

from alphapilot.validation.baselines import build_baseline_report


def test_baselines_include_no_trade_and_diagnostic_directional_reference() -> None:
    trades = [
        {
            "instrumentId": "BTC-USDT-SWAP",
            "entryTimestampMs": 1,
            "exitTimestampMs": 2,
            "entryReferencePrice": 100.0,
            "exitReferencePrice": 110.0,
            "direction": "long",
        },
        {
            "instrumentId": "ETH-USDT-SWAP",
            "entryTimestampMs": 1,
            "exitTimestampMs": 2,
            "entryReferencePrice": 200.0,
            "exitReferencePrice": 180.0,
            "direction": "long",
        },
    ]

    report = build_baseline_report(trades, direction="long")

    assert report["noTrade"]["returnPct"] == 0.0
    assert report["simpleDirectional"]["instrumentCount"] == 2
    assert report["simpleDirectional"]["equalWeightReturnPct"] == 0.0
    assert report["simpleDirectional"]["diagnosticOnly"] is True
