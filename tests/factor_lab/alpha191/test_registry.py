from __future__ import annotations

from alphapilot.factor_lab.expression_parser import parse_expression
from alphapilot.factor_lab.alpha191.registry import build_alpha191_registry


def test_registry_contains_all_191_metadata_records() -> None:
    registry = build_alpha191_registry()

    assert len(registry) == 191
    assert [item.factor_id for item in registry] == [f"alpha191_{index:03d}" for index in range(1, 192)]


def test_unreviewed_formula_is_not_silently_implemented() -> None:
    registry = build_alpha191_registry()
    unresolved = [item for item in registry if item.formula_status == "待人工确认"]

    assert unresolved
    assert all(item.canonical_formula is None for item in unresolved)
    assert all(item.crypto_adaptation_status == "待人工确认" for item in unresolved)


def test_registry_implementation_hash_is_deterministic() -> None:
    first = build_alpha191_registry()
    second = build_alpha191_registry()

    assert [item.implementation_hash for item in first] == [item.implementation_hash for item in second]


def test_every_reviewed_formula_passes_the_whitelist_parser() -> None:
    reviewed = [item for item in build_alpha191_registry() if item.canonical_formula]

    assert len(reviewed) == 8
    for item in reviewed:
        parse_expression(item.canonical_formula or "")
