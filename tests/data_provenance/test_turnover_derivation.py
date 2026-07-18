from __future__ import annotations

from alphapilot.data_provenance.turnover_derivation import derive_quote_turnover


def test_direct_quote_turnover_is_exact() -> None:
    result = derive_quote_turnover(
        volume=1_250.0,
        low=99.0,
        close=101.0,
        semantic_type="exact_quote_turnover",
    )
    assert result["value"] == 1_250.0
    assert result["evidenceType"] == "exact_quote_turnover"
    assert result["isExact"] is True


def test_verified_base_volume_uses_low_as_conservative_lower_bound() -> None:
    result = derive_quote_turnover(
        volume=10.0,
        low=99.0,
        close=101.0,
        semantic_type="verified_base_volume",
    )
    assert result["value"] == 990.0
    assert result["evidenceType"] == "conservative_quote_turnover_lower_bound"
    assert result["isExact"] is False
    assert result["formula"] == "candle_low * base_volume"


def test_close_times_base_volume_is_never_labeled_exact() -> None:
    result = derive_quote_turnover(
        volume=10.0,
        low=99.0,
        close=101.0,
        semantic_type="verified_base_volume",
    )
    assert result["value"] != 1_010.0
    assert "close" not in result["formula"]


def test_contract_volume_fails_closed_without_full_metadata() -> None:
    result = derive_quote_turnover(
        volume=10.0,
        low=99.0,
        close=101.0,
        semantic_type="verified_contract_volume",
        contract_metadata={"contractSize": 0.01},
    )
    assert result["status"] == "capacity_semantics_unavailable"
    assert result["value"] is None
