from __future__ import annotations

import pytest

from alphapilot.validation.checkpoint import load_checkpoint, save_checkpoint


def test_checkpoint_round_trip_is_bound_to_preregistration(tmp_path) -> None:
    path = tmp_path / "checkpoint.json"
    save_checkpoint(
        path,
        preregistration_hash="locked_hash",
        completed={"candidate_a": {"status": "failed_signal"}},
    )

    loaded = load_checkpoint(path, preregistration_hash="locked_hash")

    assert loaded["completed"]["candidate_a"]["status"] == "failed_signal"


def test_checkpoint_rejects_different_preregistration(tmp_path) -> None:
    path = tmp_path / "checkpoint.json"
    save_checkpoint(path, preregistration_hash="one", completed={})

    with pytest.raises(ValueError, match="preregistration hash mismatch"):
        load_checkpoint(path, preregistration_hash="two")
