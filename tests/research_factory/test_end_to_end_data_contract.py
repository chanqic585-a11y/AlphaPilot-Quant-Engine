from __future__ import annotations

from alphapilot.research_factory.end_to_end_data_contract import (
    build_end_to_end_data_contract,
)


def _candidate() -> dict:
    return {
        "candidateId": "auto-trend_failure-reversal-4h-short-v2",
        "requiredFields": ["open", "high", "low", "close"],
    }


def test_end_to_end_dependency_union_is_explicit_and_deterministic() -> None:
    contract = build_end_to_end_data_contract(
        candidate_spec=_candidate(),
        ranking_required_fields=["ranking_score"],
        exit_required_fields=["atr"],
        capital_required_fields=["quote_turnover", "current_equity"],
        cost_required_fields=["fee_rate", "slippage_rate"],
        benchmark_required_fields=["benchmark_return"],
        statistical_required_fields=["fold_identity"],
        demo_execution_required_fields=["instrument_id", "tick_size", "lot_size"],
        optional_diagnostic_fields=["reported_volume"],
    )

    assert contract["signalRequiredFields"] == ["close", "high", "low", "open"]
    assert contract["formalRequiredFields"] == [
        "atr",
        "benchmark_return",
        "close",
        "current_equity",
        "fee_rate",
        "high",
        "low",
        "open",
        "quote_turnover",
        "ranking_score",
        "slippage_rate",
    ]
    assert contract["demoRequiredFields"] == [
        *contract["formalRequiredFields"],
        "instrument_id",
        "lot_size",
        "tick_size",
    ]
    assert "fold_identity" not in contract["formalRequiredFields"]
    assert contract["contractHash"].startswith("end_to_end_data_contract_")


def test_contract_keeps_reported_volume_optional_when_capital_requires_turnover() -> None:
    contract = build_end_to_end_data_contract(
        candidate_spec=_candidate(),
        capital_required_fields=["quote_turnover"],
        optional_diagnostic_fields=["reported_volume"],
    )

    assert "reported_volume" not in contract["formalRequiredFields"]
    assert contract["optionalDiagnosticFields"] == ["reported_volume"]
    assert "quote_turnover" in contract["capitalRequiredFields"]
