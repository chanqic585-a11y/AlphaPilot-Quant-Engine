from __future__ import annotations

from pathlib import Path

from alphapilot.reference_strategy_research.candidates import build_selected_candidates
from alphapilot.reference_strategy_research.inventory import build_candidate_inventory
from alphapilot.reference_strategy_research.package_loader import load_reference_package


def test_inventory_selects_incremental_candidate_and_dedupes_turtle(
    reference_package_zip: Path,
) -> None:
    package = load_reference_package(reference_package_zip)
    rows = build_candidate_inventory(package.candidates)
    by_id = {row["candidateId"]: row for row in rows}

    assert by_id["ref_utc_session_range_breakout_1h_v1"]["disposition"] == "selected_bounded_research"
    assert by_id["ref_turtle_donchian_20_10_4h_v1"]["disposition"] == "duplicate_existing"
    assert by_id["ref_turtle_donchian_20_10_4h_v1"]["overlapWith"] == "crypto_tsmom_turtle_v1"


def test_selected_parent_candidates_expand_to_four_advisory_directional_specs() -> None:
    package_candidates = [
        {
            "candidateId": "ref_utc_session_range_breakout_1h_v1",
            "marketHypothesis": "Frozen UTC range repricing.",
        },
        {
            "candidateId": "ref_pa_breakout_failure_second_entry_4h_v1",
            "marketHypothesis": "Second failed breakout traps late participants.",
        },
    ]

    candidates = build_selected_candidates(package_candidates)

    assert len(candidates) == 4
    assert {(row.timeframe, row.direction) for row in candidates} == {
        ("1h", "long"),
        ("1h", "short"),
        ("4h", "long"),
        ("4h", "short"),
    }
    assert all(row.schemaVersion == "phase3c_candidate_v2" for row in candidates)
    assert all(row.targetR is None for row in candidates)
    assert all(row.exitPolicy is not None and not row.exitPolicy.initialStopMayWiden for row in candidates)
