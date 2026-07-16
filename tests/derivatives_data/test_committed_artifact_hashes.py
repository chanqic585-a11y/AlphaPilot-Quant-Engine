from __future__ import annotations

import hashlib
from pathlib import Path


def test_committed_evidence_sidecars_survive_git_checkout() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    attributes = repo_root / ".gitattributes"

    assert attributes.exists()
    attribute_text = attributes.read_text(encoding="utf-8")
    assert "reports/derivatives_data/*.csv text eol=lf" in attribute_text
    assert "reports/v13_27_1_12/*.csv text eol=lf" in attribute_text
    assert "reports/v13_27_1_12/*.json text eol=lf" in attribute_text
    assert "reports/v13_27_1_12/*.md text eol=lf" in attribute_text

    roots = (
        repo_root / "reports" / "derivatives_data",
        repo_root / "reports" / "v13_27_1_12",
        repo_root / "reports" / "reproducibility",
        repo_root / "reports" / "research_factory_repair",
        repo_root / "research" / "data_snapshots",
    )
    sidecars = [sidecar for root in roots for sidecar in root.glob("*.sha256")]

    assert sidecars
    for sidecar in sidecars:
        target = sidecar.with_suffix("")
        expected = sidecar.read_text(encoding="ascii").split()[0]
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        assert actual == expected, target
