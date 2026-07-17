from __future__ import annotations

import json
from pathlib import Path

from alphapilot.formal_validation.readiness_audit import (
    BASELINE_COMMIT,
    BASELINE_TAG,
    EXPECTED_V16_ARTIFACTS,
    audit_formal_prerequisites,
    audit_v16_identity,
    build_phase0_readiness_audit,
    write_phase0_evidence_bundle,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_v16_identity_bundle_and_universe_mapping_are_complete() -> None:
    result = audit_v16_identity(REPO_ROOT)

    assert result["status"] == "ready"
    assert result["baselineTag"] == BASELINE_TAG
    assert result["baselineCommit"] == BASELINE_COMMIT
    assert result["tagCommit"] == BASELINE_COMMIT
    assert result["artifactCount"] == len(EXPECTED_V16_ARTIFACTS) == 21
    assert result["missingArtifacts"] == []
    assert result["invalidArtifactHashes"] == []
    assert all(len(item["sha256"]) == 64 for item in result["artifacts"])

    universe = result["universeMapping"]
    assert universe["representativeCount"] == 10
    assert universe["formalCoreCount"] == 20
    assert universe["representativeIsSubset"] is True
    assert universe["datasetReferenceCount"] == 40
    assert universe["timeframes"] == ["1h", "4h"]


def test_formal_prerequisites_report_current_execution_inputs() -> None:
    result = audit_formal_prerequisites(REPO_ROOT)

    panel = result["statisticalPanel"]
    assert panel["rowCount"] == 38_738
    assert panel["candidateCount"] == 10
    assert panel["netRNullCount"] == 0
    assert panel["splitValues"] == ["development"]
    assert panel["foldIds"] == ["representative_prefilter"]
    assert panel["dailyPanelFeasible"] is True
    assert panel["formalWalkForwardEvidencePresent"] is False

    assert result["purgedWalkForward"]["available"] is True
    assert result["capitalCompetition"]["available"] is True
    assert result["capitalCompetition"]["frozenForV17"] is False
    assert result["freqtrade"]["packageAvailable"] is False
    assert result["freqtrade"]["s01TranslationAvailable"] is True
    assert result["freqtrade"]["timerangeIoGuardAvailable"] is True


def test_phase0_bundle_is_fail_closed_and_hash_manifested(tmp_path: Path) -> None:
    audit = build_phase0_readiness_audit(REPO_ROOT)

    assert audit["route"] == "blocked"
    blocker_codes = {item["code"] for item in audit["blockers"]}
    assert "locked_oos_identity_incomplete" in blocker_codes
    assert "formal_split_policy_not_frozen" in blocker_codes
    assert "freqtrade_runtime_missing" in blocker_codes
    assert "s01_freqtrade_translation_missing" not in blocker_codes
    assert "timerange_io_guard_missing" not in blocker_codes

    written = write_phase0_evidence_bundle(audit, tmp_path)

    expected = {
        "phase0_readiness_audit.json",
        "phase0_readiness_audit.md",
        "holdout_lineage_audit.json",
        "holdout_lineage_audit.md",
        "artifact_manifest.json",
    }
    assert {path.name for path in written} == expected
    manifest = json.loads((tmp_path / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == "formal_validation_phase0_manifest_v1"
    assert len(manifest["artifacts"]) == 4
    assert all(len(item["sha256"]) == 64 for item in manifest["artifacts"])
