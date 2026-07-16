from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphapilot.derivatives_data.snapshot_freezer import freeze_data_snapshot


def _audits() -> dict[str, object]:
    return {
        "createdAt": "2026-07-16T00:00:00Z",
        "auditStatuses": {
            "apiCapability": "completed",
            "dataQuality": "completed",
            "pitUniverse": "completed",
            "familyReadiness": "completed",
        },
        "sourceManifestHashes": ["sha256:source"],
        "normalizedHashes": ["sha256:normalized"],
        "derivedHashes": ["sha256:derived"],
        "pitHash": "sha256:pit",
        "familyReadiness": {"status": "data_not_ready"},
    }


def test_snapshot_requires_all_audits_before_freeze(tmp_path: Path) -> None:
    audits = _audits()
    audits["auditStatuses"] = {"apiCapability": "completed"}

    with pytest.raises(ValueError, match="audits must be completed"):
        freeze_data_snapshot(
            audits=audits,
            output_root=tmp_path,
            git_commit="abc123",
            environment_hash="sha256:environment",
        )


def test_snapshot_is_stable_data_only_and_writes_canonical_json(tmp_path: Path) -> None:
    first = freeze_data_snapshot(
        audits=_audits(),
        output_root=tmp_path,
        git_commit="abc123",
        environment_hash="sha256:environment",
    )
    second = freeze_data_snapshot(
        audits=_audits(),
        output_root=tmp_path,
        git_commit="abc123",
        environment_hash="sha256:environment",
    )

    assert first["snapshotId"] == second["snapshotId"]
    assert first["snapshotHash"] == second["snapshotHash"]
    assert "strategyResults" not in first
    assert "holdoutResults" not in first
    assert first["containsStrategyResults"] is False
    assert first["containsHoldoutResults"] is False
    path = tmp_path / f"{first['snapshotId']}.json"
    assert json.loads(path.read_text(encoding="utf-8"))["snapshotHash"] == first["snapshotHash"]
