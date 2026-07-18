from __future__ import annotations

from pathlib import Path

from alphapilot.scripts.prepare_v18_3_fold_ranking_closure import (
    _candidate_neutral_import_audit,
    _synthetic_second_candidate_fixture,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_v18_3_core_has_no_s01_import_and_uses_dynamic_artifact_identity() -> None:
    audit = _candidate_neutral_import_audit(REPO_ROOT)
    assert audit["status"] == "passed"
    assert audit["formalCoreImportsS01Module"] is False
    assert audit["candidateAdapterBoundaryPresent"] is True
    assert audit["dynamicArtifactIdentityPresent"] is True


def test_v18_3_second_candidate_fixture_uses_shared_adapter_contract() -> None:
    fixture = _synthetic_second_candidate_fixture(REPO_ROOT)
    assert fixture["status"] == "passed"
    assert fixture["candidateId"] == "synthetic_second_candidate_fixture"
    assert fixture["candidateId"] != "s01_bear_idiosyncratic_selloff_recovery_4h"
    assert fixture["bindingPassed"] is True
    assert fixture["signalIdentityResolved"] is True
