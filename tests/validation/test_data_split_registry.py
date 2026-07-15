from __future__ import annotations

from alphapilot.validation.data_split_registry import (
    audit_split_contamination,
    build_split_manifest,
)
from alphapilot.validation.locked_sample_protocol import sample_requirement


def _manifest(**overrides):
    payload = {
        "development_range": ("2020-01-01", "2022-12-31"),
        "validation_range": ("2023-01-01", "2023-12-31"),
        "locked_range": ("2024-01-01", "2025-12-31"),
        "development_symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
        "locked_symbols": ["SOL-USDT-SWAP"],
        "used_for_selection_ranges": [("2020-01-01", "2023-12-31")],
        "used_for_selection_symbols": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
    }
    payload.update(overrides)
    return build_split_manifest(**payload)


def test_split_manifest_hash_is_immutable_and_order_independent() -> None:
    first = _manifest()
    second = _manifest(
        development_symbols=["ETH-USDT-SWAP", "BTC-USDT-SWAP"],
        used_for_selection_symbols=["ETH-USDT-SWAP", "BTC-USDT-SWAP"],
    )

    assert first.split_manifest_hash == second.split_manifest_hash
    assert audit_split_contamination(first).potential_leakage_flags == []


def test_locked_range_overlap_is_detected() -> None:
    manifest = _manifest(
        used_for_selection_ranges=[("2020-01-01", "2024-06-30")]
    )

    audit = audit_split_contamination(manifest)

    assert "locked_range_used_for_selection" in audit.potential_leakage_flags


def test_locked_symbol_overlap_is_detected() -> None:
    manifest = _manifest(
        used_for_selection_symbols=["BTC-USDT-SWAP", "SOL-USDT-SWAP"]
    )

    audit = audit_split_contamination(manifest)

    assert "locked_symbol_used_for_selection" in audit.potential_leakage_flags


def test_one_day_30_to_49_trades_is_exploratory_only() -> None:
    exploratory = sample_requirement(
        timeframe="1d", duration_days=400, trade_count=40, effective_trade_count=40
    )
    hard = sample_requirement(
        timeframe="1d", duration_days=400, trade_count=55, effective_trade_count=52
    )

    assert exploratory.status == "exploratory_only"
    assert exploratory.hard_evidence_eligible is False
    assert hard.status == "sufficient"
    assert hard.hard_evidence_eligible is True

