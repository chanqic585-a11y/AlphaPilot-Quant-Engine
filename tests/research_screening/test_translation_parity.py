from __future__ import annotations

from alphapilot.research_screening.translation_parity import evaluate_translation_parity


def _trade(index: int) -> dict[str, object]:
    return {
        "signalId": f"signal-{index}",
        "symbol": "BTC-USDT-SWAP",
        "direction": "long",
        "decisionBar": f"2026-01-01T{index % 24:02d}:00:00Z",
        "entryBar": f"2026-01-01T{index % 24:02d}:05:00Z",
        "exitTimestamp": f"2026-01-01T{index % 24:02d}:30:00Z",
        "exitReasonClass": "target",
        "entryPrice": 100.0,
        "exitPrice": 110.0,
        "grossR": 2.1,
        "feesR": 0.04,
        "fundingR": 0.01,
        "slippageR": 0.02,
        "netR": 2.03,
    }


def test_identity_must_match_exactly_without_missing_or_extra_trades() -> None:
    reference = [_trade(1), _trade(2)]
    implementation = [_trade(1)]

    result = evaluate_translation_parity(reference, implementation)

    assert result["identityMatchRatio"] == 0.5
    assert result["translationParityPassed"] is False
    assert len(result["missingTradeIdentities"]) == 1


def test_numeric_tolerance_allows_only_explained_remainder_above_99_percent() -> None:
    reference = [_trade(index) for index in range(100)]
    implementation = [_trade(index) for index in range(100)]
    implementation[0]["entryPrice"] = 100.5
    explanation_key = "signal-0|BTC-USDT-SWAP|long|2026-01-01T00:00:00Z|2026-01-01T00:05:00Z|2026-01-01T00:30:00Z|target|entryPrice"

    unexplained = evaluate_translation_parity(
        reference,
        implementation,
        numeric_tolerances={"entryPrice": 0.01},
    )
    explained = evaluate_translation_parity(
        reference,
        implementation,
        numeric_tolerances={"entryPrice": 0.01},
        difference_explanations={explanation_key: "documented engine rounding"},
    )

    assert unexplained["numericWithinToleranceRatio"] >= 0.99
    assert unexplained["translationParityPassed"] is False
    assert explained["translationParityPassed"] is True
