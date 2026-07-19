from pathlib import Path

import pytest

from alphapilot.scripts.audit_v36_tsmom_formal_readiness import (
    _snapshot_manifest_path,
)


def test_snapshot_manifest_path_accepts_persisted_audit_shapes(tmp_path: Path) -> None:
    path = tmp_path / "snapshot.json"

    assert _snapshot_manifest_path({"snapshotManifestPath": str(path)}) == path
    assert _snapshot_manifest_path(
        {"snapshotAudit": {"snapshotManifestPath": str(path)}}
    ) == path
    assert _snapshot_manifest_path(
        {"developmentReplay": {"snapshotManifestPath": str(path)}}
    ) == path


def test_snapshot_manifest_path_fails_closed_when_reference_is_absent() -> None:
    with pytest.raises(ValueError, match="snapshot_manifest_path_missing"):
        _snapshot_manifest_path({"campaignId": "fixture"})
