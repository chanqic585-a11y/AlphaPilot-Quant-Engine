from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from alphapilot.reference_strategy_research.package_loader import load_reference_package


def test_loader_verifies_manifest_and_candidate_hashes(reference_package_zip: Path) -> None:
    package = load_reference_package(reference_package_zip)

    assert package.manifest["candidateCount"] == 3
    assert len(package.candidates) == 3
    assert package.candidates[0]["candidateId"] == "ref_utc_session_range_breakout_1h_v1"
    assert len(package.archiveSha256) == 64
    assert package.sourceFilesLoaded is False


def test_loader_rejects_tampered_candidate_file(reference_package_zip: Path, tmp_path: Path) -> None:
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(reference_package_zip) as source, zipfile.ZipFile(tampered, "w") as target:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename.endswith("candidate_specs.json"):
                payload = payload.replace(b"Frozen UTC", b"Changed UTC")
            target.writestr(item, payload)

    with pytest.raises(ValueError, match="file hash mismatch"):
        load_reference_package(tampered)
