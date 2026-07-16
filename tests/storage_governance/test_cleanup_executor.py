from pathlib import Path

import pytest

from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.storage_governance.cleanup_executor import execute_cleanup, write_artifact_manifest


def _plan(old: Path, authority: Path) -> dict:
    return {
        "schemaVersion": "storage_cleanup_plan_v1",
        "dataRoot": str(old.parent.resolve()),
        "candidates": [
            {
                "path": str(old.resolve()),
                "sha256": sha256_file(old),
                "sizeBytes": old.stat().st_size,
                "referenceCount": 0,
                "immutableEvidence": False,
                "duplicateClass": "byte_identical",
                "authoritativePath": str(authority.resolve()),
                "authoritativeSha256": sha256_file(authority),
                "contentVerified": True,
            }
        ],
    }


def test_dry_run_does_not_delete(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    old = data_root / "old.bin"
    authority = data_root / "authority.bin"
    old.write_bytes(b"same")
    authority.write_bytes(b"same")

    result = execute_cleanup(_plan(old, authority), data_root=data_root, apply_cleanup=False)

    assert old.exists()
    assert result["deletedFileCount"] == 0
    assert result["verifiedCandidateCount"] == 1


def test_apply_deletes_only_verified_candidate(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    old = data_root / "old.bin"
    authority = data_root / "authority.bin"
    old.write_bytes(b"same")
    authority.write_bytes(b"same")

    result = execute_cleanup(_plan(old, authority), data_root=data_root, apply_cleanup=True)

    assert not old.exists()
    assert authority.exists()
    assert result["deletedFileCount"] == 1


def test_executor_rejects_candidate_outside_authorized_root(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    outside = tmp_path / "outside.bin"
    authority = data_root / "authority.bin"
    outside.write_bytes(b"same")
    authority.write_bytes(b"same")
    plan = _plan(outside, authority)
    plan["dataRoot"] = str(data_root.resolve())

    with pytest.raises(ValueError, match="outside authorized data root"):
        execute_cleanup(plan, data_root=data_root, apply_cleanup=True)

    assert outside.exists()


def test_executor_rejects_plan_for_a_different_data_root(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    other_root = tmp_path / "other"
    data_root.mkdir()
    other_root.mkdir()
    old = data_root / "old.bin"
    authority = data_root / "authority.bin"
    old.write_bytes(b"same")
    authority.write_bytes(b"same")
    plan = _plan(old, authority)
    plan["dataRoot"] = str(other_root.resolve())

    with pytest.raises(ValueError, match="plan data root does not match"):
        execute_cleanup(plan, data_root=data_root, apply_cleanup=True)

    assert old.exists()
    assert authority.exists()


def test_artifact_manifest_includes_apply_and_integrity_reports(tmp_path: Path) -> None:
    output = tmp_path / "reports"
    output.mkdir()
    (output / "cleanup_apply_manifest.json").write_text("{}\n", encoding="utf-8")
    (output / "cleanup_integrity_check.json").write_text("{}\n", encoding="utf-8")

    manifest = write_artifact_manifest(output, data_root=tmp_path / "data")

    assert set(manifest["artifacts"]) == {
        "cleanup_apply_manifest.json",
        "cleanup_integrity_check.json",
    }
