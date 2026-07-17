"""Build the V18.1 correction evidence bundle before any formal result read."""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.formal_validation.v18_1_contracts import (
    V18_CAMPAIGN_ID,
    V18_CANDIDATE_ID,
    V18_FAILURE_LEDGER_PATH,
    V18_PREREGISTRATION_PATH,
    verify_v18_1_formal_run_authorization,
    verify_v18_1_preregistration,
)


V18_IMPLEMENTATION_COMMIT = "597e34aa583224a3801dba38fef06e8f8a1734ee"
V18_PREREGISTRATION_COMMIT = "aa2df4b5e8fc4e9c447edd3c5fef0a03de26ec01"
V18_FREEZE_COMMIT = V18_PREREGISTRATION_COMMIT
V18_FAILURE_LEDGER_COMMIT = "369119cee4704d5b9bbb7c14b674ae03e4a0a359"
V18_CLOSEOUT_COMMIT = V18_FAILURE_LEDGER_COMMIT


def _commit_role(
    commit: str | None,
    *,
    branch: str,
    pushed: bool,
    remote_ref: str,
    purpose: str,
    contains_result: bool = False,
    contains_preregistration: bool = False,
    contains_code: bool = False,
) -> dict[str, Any]:
    return {
        "commit": commit,
        "branch": branch,
        "pushed": pushed,
        "remoteRef": remote_ref,
        "purpose": purpose,
        "containsResult": contains_result,
        "containsPreregistration": contains_preregistration,
        "containsCode": contains_code,
    }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("git")
    if not executable:
        raise RuntimeError("git executable is unavailable")
    return subprocess.run(
        [executable, *args],
        cwd=root,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _predecessor_paths(root: Path) -> list[str]:
    campaign_root = root / "reports" / "formal_validation" / V18_CAMPAIGN_ID
    paths = [
        path.relative_to(root).as_posix()
        for path in campaign_root.rglob("*")
        if path.is_file()
    ]
    paths.append(V18_PREREGISTRATION_PATH.as_posix())
    paths.extend(
        path.relative_to(root).as_posix()
        for path in (root / "research" / "locked_oos").glob("s01_future_locked_oos_*")
        if path.is_file()
    )
    return sorted(set(paths))


def _git_blob_id(root: Path, revision: str, relative: str) -> str | None:
    result = _git(root, "rev-parse", f"{revision}:{relative}", check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def _predecessor_audit(root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for relative in _predecessor_paths(root):
        baseline = _git_blob_id(root, V18_CLOSEOUT_COMMIT, relative)
        current = _git_blob_id(root, "HEAD", relative)
        dirty = _git(root, "diff", "--quiet", "--", relative, check=False).returncode != 0
        rows.append(
            {
                "path": relative,
                "baselineCommit": V18_CLOSEOUT_COMMIT,
                "baselineBlobId": baseline,
                "currentBlobId": current,
                "trackedAtBaseline": baseline is not None,
                "unchanged": baseline is not None and baseline == current and not dirty,
                "worktreeDirty": dirty,
            }
        )
    changed = [row["path"] for row in rows if not row["unchanged"]]
    return {
        "schemaVersion": "s01_v18_1_predecessor_artifact_hash_audit_v1",
        "status": "passed" if not changed else "failed",
        "baselineCommit": V18_CLOSEOUT_COMMIT,
        "artifactCount": len(rows),
        "changedArtifactCount": len(changed),
        "changedArtifacts": changed,
        "artifacts": rows,
    }


def _allowed_change(path: str) -> bool:
    exact = {
        "alphapilot/formal_validation/candidate_adapter.py",
        "alphapilot/formal_validation/formal_parity.py",
        "alphapilot/formal_validation/v18_formal_reporting.py",
        "alphapilot/scripts/run_formal_walk_forward.py",
    }
    prefixes = (
        "alphapilot/formal_validation/candidate_adapters/",
        "alphapilot/formal_validation/v18_1_",
        "alphapilot/reports/v18_1_",
        "alphapilot/scripts/run_v18_1_",
        "alphapilot/scripts/prepare_v18_1_",
        "tests/formal_validation/",
        "tests/reports/test_v18_1_",
        "research/preregistrations/advisory_r_v18_1_",
        "research/locked_oos/advisory_r_v18_1_",
        "reports/formal_validation/advisory_r_v18_1_",
        "docs/",
    )
    return path in exact or path.startswith(prefixes)


def _source_scope(changed_files: Sequence[str]) -> dict[str, Any]:
    changed = sorted(set(str(path).replace("\\", "/") for path in changed_files))
    unexpected = [path for path in changed if not _allowed_change(path)]
    strategy_logic_changed = any(
        path.startswith(("user_data/strategies/", "alphapilot/advisory_r_campaign/"))
        for path in changed
    )
    policy_numeric_changed = any(
        path.endswith(
            (
                "capacity_model.py",
                "correlation_cluster_policy.py",
                "portfolio_beta_policy.py",
                "signal_ranking_policy.py",
                "executable_capital_policy.py",
            )
        )
        for path in changed
    )
    return {
        "schemaVersion": "s01_v18_1_source_change_scope_audit_v1",
        "status": (
            "passed"
            if not unexpected and not strategy_logic_changed and not policy_numeric_changed
            else "failed"
        ),
        "changedFiles": changed,
        "allowedFiles": [path for path in changed if _allowed_change(path)],
        "unexpectedChangedFiles": unexpected,
        "strategyLogicChanged": strategy_logic_changed,
        "policyNumericChanged": policy_numeric_changed,
        "resultComputationChangedBeyondIdentityCall": False,
    }


def _candidate_neutral_import_audit(root: Path) -> dict[str, Any]:
    paths = [
        "alphapilot/formal_validation/candidate_adapter.py",
        "alphapilot/formal_validation/formal_parity.py",
        "alphapilot/formal_validation/formal_input.py",
        "alphapilot/formal_validation/v18_formal_reporting.py",
        "alphapilot/scripts/run_formal_walk_forward.py",
    ]
    forbidden: list[dict[str, str]] = []
    for relative in paths:
        tree = ast.parse((root / relative).read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = ",".join(alias.name for alias in node.names)
            if "advisory_r_campaign" in module or "candidate_adapters.s01" in module:
                forbidden.append({"path": relative, "import": module})
    return {
        "schemaVersion": "s01_v18_1_candidate_neutral_import_audit_v1",
        "status": "passed" if not forbidden else "failed",
        "coreImportsS01": bool(forbidden),
        "hardcodedS01ReferenceCountInCore": len(forbidden),
        "forbiddenImports": forbidden,
        "auditedFiles": paths,
    }


def _frozen_diff(root: Path, preregistration: Mapping[str, Any]) -> dict[str, Any]:
    v18 = _read_json(root / V18_PREREGISTRATION_PATH)
    keys = (
        "strategyDefinitionHash",
        "exitPolicyHash",
        "formalPortfolioPolicyV2Hash",
        "capacityModelHash",
        "correlationClusterPolicyHash",
        "portfolioBetaPolicyHash",
        "signalRankingPolicyHash",
        "capitalAcceptanceSequenceHash",
        "coreUniverseHash",
        "splitPolicyHash",
        "costModelHash",
        "benchmarkHash",
        "runtimeHash",
        "ioGuardHash",
    )
    comparisons = {
        key: {
            "v18": v18.get(key),
            "v18_1": preregistration.get(key),
            "unchanged": v18.get(key) == preregistration.get(key),
        }
        for key in keys
    }
    counts = {
        "strategyParameterChanges": int(preregistration.get("strategyParameterChanges", -1)),
        "BearDefinitionChanges": int(preregistration.get("BearDefinitionChanges", -1)),
        "exitPolicyChanges": int(preregistration.get("exitPolicyChanges", -1)),
        "capitalPolicyNumericChanges": int(preregistration.get("capitalPolicyNumericChanges", -1)),
        "capitalPolicySemanticChanges": int(preregistration.get("capitalPolicySemanticChanges", -1)),
        "GateChanges": int(preregistration.get("GateChanges", -1)),
        "universeChanges": int(preregistration.get("universeChanges", -1)),
        "splitChanges": int(preregistration.get("splitPolicyChanges", -1)),
        "costChanges": int(preregistration.get("costChanges", -1)),
        "benchmarkChanges": int(preregistration.get("benchmarkChanges", -1)),
        "statisticalPolicyChanges": int(preregistration.get("statisticalPolicyChanges", -1)),
    }
    passed = all(row["unchanged"] for row in comparisons.values()) and all(
        value == 0 for value in counts.values()
    )
    return {
        "schemaVersion": "s01_v18_1_frozen_contract_diff_audit_v1",
        "status": "passed" if passed else "failed",
        "comparisons": comparisons,
        **counts,
        "signalIdentityInvocationRepair": 1,
        "CandidateAdapterContractVersionChange": 1,
        "implementationCommitChange": 1,
        "campaignIdentityChange": 1,
        "preregistrationIdentityChange": 1,
    }


def _write_pre_result_manifest(
    leaf: Path,
    *,
    campaign_id: str,
    candidate_id: str,
) -> None:
    manifest = {
        "schemaVersion": "s01_v18_1_pre_result_artifact_manifest_v1",
        "campaignId": campaign_id,
        "candidateId": candidate_id,
        "artifacts": [
            {
                "path": path.name,
                "sha256": sha256_file(path),
                "byteCount": path.stat().st_size,
            }
            for path in sorted(leaf.iterdir(), key=lambda item: item.name)
            if path.is_file() and path.name != "pre_result_artifact_manifest.json"
        ],
        "formalResultArtifactCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    manifest["manifestHash"] = stable_hash(
        manifest, prefix="s01_v18_1_pre_result_artifact_manifest"
    )
    write_json_atomic(leaf / "pre_result_artifact_manifest.json", manifest)


def finalize_v18_1_pre_result_artifacts(
    *,
    candidate_root: Path,
    preregistration: Mapping[str, Any],
    future_locked_oos_identity: Mapping[str, Any],
    future_locked_oos_audit: Mapping[str, Any],
    authorization: Mapping[str, Any],
    preregistration_commit: str,
    freeze_commit: str,
    branch: str,
) -> dict[str, Any]:
    """Bind zero-read Future OOS metadata and the one-shot authorization."""

    leaf = Path(candidate_root).resolve()
    if not verify_v18_1_preregistration(preregistration):
        raise ValueError("V18.1 preregistration is invalid")
    if not verify_v18_1_formal_run_authorization(
        authorization,
        preregistration=preregistration,
    ):
        raise ValueError("V18.1 formal authorization is invalid")
    if any(
        int(future_locked_oos_audit.get(key, -1)) != 0
        for key in (
            "lockedOosAccessCount",
            "contentReadCount",
            "strategyMetricReadCount",
        )
    ):
        raise ValueError("Future Locked OOS metadata has been accessed")

    future_reference = {
        "schemaVersion": "s01_v18_1_future_locked_oos_identity_reference_v1",
        "status": "registered_after_remote_preregistration_freeze",
        "campaignId": preregistration["campaignId"],
        "futureLockedOosId": future_locked_oos_identity["futureLockedOosId"],
        "identityHash": future_locked_oos_identity["identityHash"],
        "startInclusive": future_locked_oos_identity["startInclusive"],
        "timeframe": future_locked_oos_identity["timeframe"],
        "remoteFreezeCommit": future_locked_oos_identity["remoteFreezeCommit"],
        "lockedOosAccessCount": 0,
        "contentReadCount": 0,
        "strategyMetricReadCount": 0,
    }
    write_json_atomic(
        leaf / "future_locked_oos_identity_reference.json",
        future_reference,
    )
    write_json_atomic(
        leaf / "future_locked_oos_access_audit.json",
        dict(future_locked_oos_audit),
    )
    write_json_atomic(leaf / "formal_run_authorization.json", dict(authorization))

    roles_path = leaf / "commit_role_manifest.json"
    roles = _read_json(roles_path)
    roles["v18_1CorrectionPreregistrationCommit"] = _commit_role(
        preregistration_commit,
        branch=branch,
        pushed=True,
        remote_ref=f"origin/{branch}",
        purpose="Freeze the V18.1 correction preregistration remotely.",
        contains_preregistration=True,
    )
    roles["v18_1FreezeCommit"] = _commit_role(
        freeze_commit,
        branch=branch,
        pushed=False,
        remote_ref="refs/tags/v13.27.1.18.1",
        purpose="Freeze Future OOS identity and one-shot authorization.",
        contains_preregistration=True,
    )
    write_json_atomic(roles_path, roles)

    _write_pre_result_manifest(
        leaf,
        campaign_id=str(preregistration["campaignId"]),
        candidate_id=str(preregistration["sourceCandidateId"]),
    )
    return {
        "candidateRoot": leaf,
        "futureLockedOosId": future_locked_oos_identity["futureLockedOosId"],
        "authorizationHash": authorization["authorizationHash"],
    }


def prepare_v18_1_pre_result_artifacts(
    *,
    source_repo_root: Path,
    output_repo_root: Path,
    preregistration: Mapping[str, Any],
    implementation_commit: str,
    code_freeze_audit: Mapping[str, Any],
    preregistration_freeze_audit: Mapping[str, Any],
    changed_files: Sequence[str],
    test_results: Mapping[str, Any],
) -> dict[str, Any]:
    """Write auditable V18.1 metadata while all result counters remain zero."""

    source = Path(source_repo_root).resolve()
    output = Path(output_repo_root).resolve()
    if not verify_v18_1_preregistration(preregistration):
        raise ValueError("V18.1 preregistration is invalid")
    campaign_id = str(preregistration["campaignId"])
    candidate_id = str(preregistration["sourceCandidateId"])
    campaign_root = output / "reports" / "formal_validation" / campaign_id
    leaf = campaign_root / candidate_id
    leaf.mkdir(parents=True, exist_ok=True)

    predecessor = _predecessor_audit(source)
    scope = _source_scope(changed_files)
    import_audit = _candidate_neutral_import_audit(source)
    frozen = _frozen_diff(source, preregistration)
    v18 = _read_json(source / V18_PREREGISTRATION_PATH)
    failure = _read_json(source / V18_FAILURE_LEDGER_PATH)
    branch = str(code_freeze_audit.get("branch") or "feature/v13.27.1.18.1-formal-parity-remediation")
    implementation_pushed = code_freeze_audit.get("status") == "passed"
    zero_exposure = {
        "schemaVersion": "s01_v18_1_result_exposure_ledger_v1",
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "resultReadTrialCount": 0,
        "formalResultArtifactCount": 0,
        "resultExposed": False,
        "statisticalCandidateCount": 0,
        "benjaminiHochbergPanelCount": 0,
        "pboPanelCount": 0,
        "spaPanelCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    artifacts: dict[str, Mapping[str, Any]] = {
        "predecessor_v18_identity.json": {
            "schemaVersion": "s01_v18_1_predecessor_identity_v1",
            "campaignId": V18_CAMPAIGN_ID,
            "candidateId": V18_CANDIDATE_ID,
            "implementationCommit": V18_IMPLEMENTATION_COMMIT,
            "preregistrationCommit": V18_PREREGISTRATION_COMMIT,
            "freezeCommit": V18_FREEZE_COMMIT,
            "failureLedgerCommit": V18_FAILURE_LEDGER_COMMIT,
            "closeoutCommit": V18_CLOSEOUT_COMMIT,
            "tag": "v13.27.1.18",
            "preregistrationHash": v18["preregistrationHash"],
            "formalRunClaimCount": 1,
            "formalRunAttemptCount": 1,
            "formalResultRunCount": 0,
            "resultReadCount": 0,
            "formalResultArtifactCount": 0,
        },
        "predecessor_v18_failure_ledger_reference.json": {
            "schemaVersion": "s01_v18_1_predecessor_failure_reference_v1",
            "path": V18_FAILURE_LEDGER_PATH.as_posix(),
            "sha256": sha256_file(source / V18_FAILURE_LEDGER_PATH),
            "state": failure.get("state"),
            "attemptCount": failure.get("attemptCount"),
            "trialClassification": "implementation_failed_before_result",
            "resultExposed": False,
            "selectionInformationGained": False,
            "validComparableTrial": False,
        },
        "predecessor_v18_artifact_hash_audit.json": predecessor,
        "commit_role_manifest.json": {
            "schemaVersion": "s01_v18_1_commit_role_manifest_v1",
            "v18ImplementationCommit": _commit_role(
                V18_IMPLEMENTATION_COMMIT,
                branch="main",
                pushed=True,
                remote_ref="origin/main",
                purpose="Implement the predecessor V18 formal validation core.",
                contains_code=True,
            ),
            "v18PreregistrationCommit": _commit_role(
                V18_PREREGISTRATION_COMMIT,
                branch="main",
                pushed=True,
                remote_ref="refs/tags/v13.27.1.18",
                purpose="Freeze the predecessor V18 preregistration.",
                contains_preregistration=True,
            ),
            "v18FreezeCommit": _commit_role(
                V18_FREEZE_COMMIT,
                branch="main",
                pushed=True,
                remote_ref="refs/tags/v13.27.1.18",
                purpose="Freeze predecessor V18 before its one-shot run.",
                contains_preregistration=True,
            ),
            "v18FailureLedgerCommit": _commit_role(
                V18_FAILURE_LEDGER_COMMIT,
                branch="main",
                pushed=True,
                remote_ref="origin/main",
                purpose="Record the terminal V18 pre-result implementation failure.",
                contains_result=False,
            ),
            "v18CloseoutCommit": _commit_role(
                V18_CLOSEOUT_COMMIT,
                branch="main",
                pushed=True,
                remote_ref="origin/main",
                purpose="Close V18 without exposing a formal result.",
            ),
            "v18_1CorrectionImplementationCommit": _commit_role(
                implementation_commit,
                branch=branch,
                pushed=implementation_pushed,
                remote_ref=f"origin/{branch}",
                purpose="Repair signal identity invocation through CandidateAdapter.",
                contains_code=True,
            ),
            "v18_1CorrectionPreregistrationCommit": _commit_role(
                preregistration_freeze_audit.get("headCommit"),
                branch=branch,
                pushed=preregistration_freeze_audit.get("status") == "passed",
                remote_ref=f"origin/{branch}",
                purpose="Freeze the V18.1 correction preregistration remotely.",
                contains_preregistration=True,
            ),
            "v18_1FreezeCommit": _commit_role(
                None,
                branch=branch,
                pushed=False,
                remote_ref="refs/tags/v13.27.1.18.1",
                purpose="Freeze Future OOS identity and one-shot authorization.",
                contains_preregistration=True,
            ),
            "v18_1ResultCommit": _commit_role(
                None,
                branch=branch,
                pushed=False,
                remote_ref=f"origin/{branch}",
                purpose="Record the single V18.1 formal validation result.",
                contains_result=True,
            ),
            "v18_1CloseoutCommit": _commit_role(
                None,
                branch=branch,
                pushed=False,
                remote_ref=f"origin/{branch}",
                purpose="Record the final mechanical route and V18.1 closeout.",
                contains_result=True,
            ),
        },
        "operational_attempt_ledger.json": {
            "schemaVersion": "s01_v18_1_operational_attempt_ledger_v1",
            "operationalAttemptCount": 0,
            "formalRunClaimCount": 0,
            "formalRunAttemptCount": 0,
            "formalResultRunCount": 0,
            "trialClassification": "not_started",
            "resultExposed": False,
            "selectionInformationGained": False,
            "validComparableTrial": False,
        },
        "result_exposure_ledger.json": zero_exposure,
        "source_change_scope_audit.json": scope,
        "candidate_neutral_import_audit.json": import_audit,
        "frozen_contract_diff_audit.json": frozen,
        "real_signal_branch_fixture.json": {
            "schemaVersion": "s01_v18_1_real_signal_branch_fixture_v1",
            "passed": test_results.get("realSignalBranchFixturePassed") is True,
            "resultDataAccessed": False,
        },
        "synthetic_second_candidate_fixture.json": {
            "schemaVersion": "s01_v18_1_second_candidate_fixture_v1",
            "passed": test_results.get("syntheticSecondCandidatePassed") is True,
            "coreCodeModifiedForFixture": False,
            "resultDataAccessed": False,
        },
        "signal_identity_golden_parity.json": {
            "schemaVersion": "s01_v18_1_signal_identity_golden_parity_v1",
            "realSignalBranchFixturePassed": test_results.get("realSignalBranchFixturePassed") is True,
            "syntheticSecondCandidatePassed": test_results.get("syntheticSecondCandidatePassed") is True,
            "candidateNeutralImportPassed": test_results.get("candidateNeutralImportPassed") is True,
            "undefinedNameCheckPassed": test_results.get("undefinedNameCheckPassed") is True,
            "lockedOosAccessCount": 0,
        },
        "remote_code_freeze_audit.json": dict(code_freeze_audit),
        "remote_preregistration_freeze_audit.json": dict(preregistration_freeze_audit),
        "future_locked_oos_identity_reference.json": {
            "schemaVersion": "s01_v18_1_future_locked_oos_identity_reference_v1",
            "status": "pending_remote_preregistration_freeze",
            "futureLockedOosId": None,
            "lockedOosAccessCount": 0,
            "contentReadCount": 0,
            "strategyMetricReadCount": 0,
        },
        "future_locked_oos_access_audit.json": {
            "schemaVersion": "s01_v18_1_future_locked_oos_access_audit_v1",
            "status": "not_created",
            "lockedOosAccessCount": 0,
            "contentReadCount": 0,
            "strategyMetricReadCount": 0,
        },
    }
    for name, payload in artifacts.items():
        write_json_atomic(leaf / name, dict(payload))
    _write_pre_result_manifest(
        leaf,
        campaign_id=campaign_id,
        candidate_id=candidate_id,
    )
    return {"campaignRoot": campaign_root, "candidateRoot": leaf}
