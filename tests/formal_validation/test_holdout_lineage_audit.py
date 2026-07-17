from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphapilot.formal_validation.holdout_lineage_audit import (
    audit_holdout_lineage,
    load_metadata_json,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_holdout_audit_uses_metadata_and_preserves_zero_access() -> None:
    result = audit_holdout_lineage(REPO_ROOT)

    assert result["status"] == "limitation"
    assert result["recordedAccessCount"] == 0
    assert result["accessCountsConsistent"] is True
    assert result["accessCountSources"] == {
        "campaignSummary": 0,
        "correctionManifest": 0,
        "prefilterResults": 0,
        "preregistration": 0,
        "routeDecision": 0,
    }
    assert result["unlockLedgerPresent"] is False
    assert result["holdoutBoundaryPresent"] is False
    assert result["holdoutHashPresent"] is False
    assert result["cleanLockedOosAvailable"] is False
    assert set(result["missingIdentityFields"]) == {"holdoutBoundary", "holdoutHash"}


def test_metadata_loader_rejects_possible_holdout_content(tmp_path: Path) -> None:
    safe_path = tmp_path / "campaign_summary.json"
    safe_path.write_text(json.dumps({"lockedOosAccessCount": 0}), encoding="utf-8")
    assert load_metadata_json(safe_path)["lockedOosAccessCount"] == 0

    forbidden = tmp_path / "locked_oos_data" / "metrics.json"
    forbidden.parent.mkdir()
    forbidden.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Locked OOS content path"):
        load_metadata_json(forbidden)
