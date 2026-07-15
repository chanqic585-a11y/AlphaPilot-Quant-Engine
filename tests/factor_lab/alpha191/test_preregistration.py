from __future__ import annotations

import json
from pathlib import Path

from alphapilot.factor_lab.alpha191.preregistration import build_seed_preregistration
from alphapilot.factor_lab.alpha191.registry import build_alpha191_registry


def test_seed_preregistration_is_bounded_and_uses_only_reviewed_formulas() -> None:
    payload = build_seed_preregistration()
    reviewed = {item.factor_id for item in build_alpha191_registry() if item.canonical_formula}
    factor_ids = [item["factorId"] for item in payload["seedFactors"]]

    assert 0 < len(factor_ids) <= 32
    assert set(factor_ids) <= reviewed
    assert payload["selectionUsedPerformance"] is False
    assert payload["allowedTimeframes"] == ["1h", "4h", "1d"]


def test_seed_windows_are_mapped_by_economic_time_span() -> None:
    payload = build_seed_preregistration()
    alpha_014 = next(item for item in payload["seedFactors"] if item["factorId"] == "alpha191_014")

    assert alpha_014["economicWindowDays"] == [5]
    assert alpha_014["periodsByTimeframe"] == {
        "1d": [5],
        "4h": [30],
        "1h": [120],
    }


def test_committed_preregistration_matches_the_builder() -> None:
    path = Path("research/factor_preregistrations/alpha191_seed_v1.json")
    committed = json.loads(path.read_text(encoding="utf-8"))

    assert committed == build_seed_preregistration()
