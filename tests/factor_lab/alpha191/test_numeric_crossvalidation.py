from __future__ import annotations

from alphapilot.factor_lab.alpha191.numeric_crossvalidation import run_numeric_crossvalidation


def test_seed_numeric_crossvalidation_has_no_unexpected_mismatch() -> None:
    report = run_numeric_crossvalidation()

    assert report["seedCount"] == 8
    assert report["unexpectedMismatchCount"] == 0
    assert report["formulaConflictCount"] == 0
    assert {item["status"] for item in report["results"]} <= {
        "exact_match",
        "tolerance_match",
    }
    assert all(item["containsInfinity"] is False for item in report["results"])
