from __future__ import annotations

import json
from pathlib import Path

from alphapilot.formal_validation.freqtrade_io_fixture import (
    build_phase2_io_fixture_evidence,
)


def test_fixture_builder_emits_isolated_zero_result_evidence(tmp_path: Path) -> None:
    fixture_root = tmp_path / "non_holdout_fixture"
    evidence_root = tmp_path / "evidence"
    locked_oos_root = tmp_path / "future_locked_oos"

    result = build_phase2_io_fixture_evidence(
        fixture_root=fixture_root,
        evidence_root=evidence_root,
        forbidden_locked_oos_root=locked_oos_root,
    )

    assert result["status"] == "passed"
    assert result["fixtureOnly"] is True
    assert result["formalResultCount"] == 0
    assert result["lockedOosAccessCount"] == 0
    assert result["releaseCount"] == 0
    assert result["demoArm"] is False
    assert result["orderCount"] == 0
    assert locked_oos_root.exists() is False

    required = {
        "freqtrade_io_guard_readiness.json",
        "non_holdout_data_root_manifest.json",
        "freqtrade_io_fixture_access_log.json",
        "freqtrade_io_fixture_access_log.jsonl",
    }
    assert required.issubset({path.name for path in evidence_root.iterdir()})

    readiness = json.loads(
        (evidence_root / "freqtrade_io_guard_readiness.json").read_text("utf-8")
    )
    manifest = json.loads(
        (evidence_root / "non_holdout_data_root_manifest.json").read_text("utf-8")
    )
    access = json.loads(
        (evidence_root / "freqtrade_io_fixture_access_log.json").read_text("utf-8")
    )

    assert readiness["status"] == "passed"
    assert readiness["networkMode"] == "none"
    assert readiness["repositoryReadOnly"] is True
    assert readiness["lockedOosMounted"] is False
    assert readiness["accessAudit"]["allowedReadCount"] == 1
    assert readiness["accessAudit"]["unauthorizedAttemptCount"] == 0
    assert manifest["fixtureOnly"] is True
    assert manifest["allowedFileCount"] == 1
    assert manifest["files"][0]["relativePath"].endswith("-4h-futures.feather")
    assert access["eventCount"] == 1
    assert access["events"][0]["allowed"] is True
    assert access["events"][0]["reason"] == "allowlisted_read"
