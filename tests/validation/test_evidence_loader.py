from __future__ import annotations

import json

import pytest

from alphapilot.validation.evidence_loader import load_verified_json, sha256_file


def test_verified_json_accepts_matching_sha256(tmp_path) -> None:
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"trades": []}), encoding="utf-8")

    payload = load_verified_json(path, expected_sha256=sha256_file(path))

    assert payload == {"trades": []}


def test_verified_json_rejects_tampered_file(tmp_path) -> None:
    path = tmp_path / "report.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_verified_json(path, expected_sha256="0" * 64)
