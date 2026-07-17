from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from alphapilot.formal_validation.v18_1_contracts import (
    build_v18_1_formal_run_authorization,
    build_v18_1_future_locked_oos_identity,
    build_v18_1_preregistration,
)
from alphapilot.reports.v18_1_pre_result_artifacts import (
    finalize_v18_1_pre_result_artifacts,
    prepare_v18_1_pre_result_artifacts,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_v18_1_pre_result_bundle_preserves_v18_and_contains_no_results(
    tmp_path: Path,
) -> None:
    del tmp_path
    short_root = Path(tempfile.mkdtemp(prefix="v181-", dir="D:/Codex-Workspace"))
    preregistration = build_v18_1_preregistration(
        REPO_ROOT,
        implementation_commit="c" * 40,
        frozen_at="2026-07-18T04:00:00Z",
    )
    try:
        result = prepare_v18_1_pre_result_artifacts(
            source_repo_root=REPO_ROOT,
            output_repo_root=short_root,
            preregistration=preregistration,
            implementation_commit="c" * 40,
            code_freeze_audit={"status": "passed", "pushed": True},
            preregistration_freeze_audit={"status": "passed", "hashMatch": True},
            changed_files=[
                "alphapilot/formal_validation/candidate_adapter.py",
                "alphapilot/formal_validation/formal_parity.py",
                "tests/formal_validation/test_formal_parity.py",
            ],
            test_results={
                "realSignalBranchFixturePassed": True,
                "syntheticSecondCandidatePassed": True,
                "candidateNeutralImportPassed": True,
                "undefinedNameCheckPassed": True,
            },
        )

        root = result["campaignRoot"] / preregistration["sourceCandidateId"]
        required = {
            "predecessor_v18_identity.json",
            "predecessor_v18_failure_ledger_reference.json",
            "predecessor_v18_artifact_hash_audit.json",
            "commit_role_manifest.json",
            "operational_attempt_ledger.json",
            "result_exposure_ledger.json",
            "source_change_scope_audit.json",
            "candidate_neutral_import_audit.json",
            "frozen_contract_diff_audit.json",
            "real_signal_branch_fixture.json",
            "synthetic_second_candidate_fixture.json",
            "signal_identity_golden_parity.json",
            "remote_code_freeze_audit.json",
            "remote_preregistration_freeze_audit.json",
            "future_locked_oos_identity_reference.json",
            "future_locked_oos_access_audit.json",
        }
        assert required <= {path.name for path in root.iterdir()}

        predecessor = json.loads(
            (root / "predecessor_v18_artifact_hash_audit.json").read_text()
        )
        roles = json.loads((root / "commit_role_manifest.json").read_text())
        scope = json.loads((root / "source_change_scope_audit.json").read_text())
        frozen = json.loads((root / "frozen_contract_diff_audit.json").read_text())
        exposure = json.loads((root / "result_exposure_ledger.json").read_text())
        assert predecessor["status"] == "passed"
        assert predecessor["changedArtifactCount"] == 0
        assert roles["v18ImplementationCommit"]["containsCode"] is True
        assert roles["v18_1CorrectionImplementationCommit"]["commit"] == "c" * 40
        assert roles["v18_1CorrectionImplementationCommit"]["pushed"] is True
        assert all(
            {
                "commit",
                "branch",
                "pushed",
                "remoteRef",
                "purpose",
                "containsResult",
                "containsPreregistration",
                "containsCode",
            }
            <= set(value)
            for key, value in roles.items()
            if key != "schemaVersion"
        )
        assert scope["unexpectedChangedFiles"] == []
        assert scope["strategyLogicChanged"] is False
        assert frozen["status"] == "passed"
        assert frozen["strategyParameterChanges"] == 0
        assert exposure["formalResultRunCount"] == 0
        assert exposure["resultReadCount"] == 0
        assert exposure["formalResultArtifactCount"] == 0
        assert exposure["lockedOosAccessCount"] == 0
        assert exposure["releaseCount"] == 0
        assert exposure["demoArm"] is False
        assert exposure["orderCount"] == 0
        assert not (root / "fold_results.json").exists()

        identity = build_v18_1_future_locked_oos_identity(
            preregistration,
            remote_freeze_commit="d" * 40,
            remote_verified_at="2026-07-18T04:00:00Z",
        )
        checks = {
            "oldV18ArtifactsModified": False,
            "oldV18LedgerModified": False,
            "realSignalBranchFixturePassed": True,
            "syntheticSecondCandidatePassed": True,
            "candidateNeutralImportPassed": True,
            "undefinedNameCheckPassed": True,
            "correctionCodePushed": True,
            "correctionPreregistrationPushed": True,
            "formalResultRunCount": 0,
            "resultReadCount": 0,
            "lockedOosAccessCount": 0,
        }
        authorization = build_v18_1_formal_run_authorization(
            preregistration,
            implementation_commit="c" * 40,
            remote_implementation_commit="c" * 40,
            remote_preregistration_commit="d" * 40,
            future_locked_oos_identity=identity,
            checks=checks,
        )
        finalize_v18_1_pre_result_artifacts(
            candidate_root=root,
            preregistration=preregistration,
            future_locked_oos_identity=identity,
            future_locked_oos_audit={
                "status": "passed",
                "lockedOosAccessCount": 0,
                "contentReadCount": 0,
                "strategyMetricReadCount": 0,
            },
            authorization=authorization,
            preregistration_commit="d" * 40,
            freeze_commit="f" * 40,
            branch="feature/v18-1",
        )

        assert json.loads((root / "formal_run_authorization.json").read_text())[
            "authorizationStatus"
        ] == "authorized"
        future_ref = json.loads(
            (root / "future_locked_oos_identity_reference.json").read_text()
        )
        roles = json.loads((root / "commit_role_manifest.json").read_text())
        assert future_ref["futureLockedOosId"] == identity["futureLockedOosId"]
        assert future_ref["lockedOosAccessCount"] == 0
        assert roles["v18_1CorrectionPreregistrationCommit"]["commit"] == "d" * 40
        assert roles["v18_1FreezeCommit"]["commit"] == "f" * 40
        assert not (root / "fold_results.json").exists()
    finally:
        shutil.rmtree(short_root, ignore_errors=True)
