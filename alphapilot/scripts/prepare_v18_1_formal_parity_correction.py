"""Prepare the remotely frozen V18.1 correction without reading results."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.formal_validation.v18_1_contracts import (
    V18_1_ADAPTER_CONTRACT_VERSION,
    build_v18_1_formal_run_authorization,
    build_v18_1_future_locked_oos_identity,
    build_v18_1_preregistration,
    verify_v18_1_preregistration,
    write_v18_1_future_locked_oos_metadata,
    write_v18_1_preregistration,
)
from alphapilot.formal_validation.v18_1_remote_freeze import (
    V18_1_TAG,
    audit_v18_1_code_freeze,
    audit_v18_1_preregistration_freeze,
)
from alphapilot.reports.v18_1_pre_result_artifacts import (
    V18_CLOSEOUT_COMMIT,
    finalize_v18_1_pre_result_artifacts,
    prepare_v18_1_pre_result_artifacts,
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _git(root: Path, *args: str, git_executable: str | None = None) -> str:
    executable = git_executable or shutil.which("git")
    if not executable:
        raise RuntimeError("git executable is unavailable")
    result = subprocess.run(
        [executable, *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _candidate_root(repo_root: Path, preregistration: dict[str, Any]) -> Path:
    return (
        repo_root
        / "reports"
        / "formal_validation"
        / str(preregistration["campaignId"])
        / str(preregistration["sourceCandidateId"])
    )


def prepare_preregistration(
    repo_root: Path,
    *,
    implementation_commit: str,
    frozen_at: str,
) -> dict[str, Any]:
    preregistration = build_v18_1_preregistration(
        repo_root,
        implementation_commit=implementation_commit,
        frozen_at=frozen_at,
    )
    path = write_v18_1_preregistration(preregistration, repo_root)
    return {
        "stage": "preregistration_created",
        "campaignId": preregistration["campaignId"],
        "candidateId": preregistration["sourceCandidateId"],
        "preregistrationHash": preregistration["preregistrationHash"],
        "path": path.relative_to(repo_root).as_posix(),
        "formalRunClaimCount": 0,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
    }


def prepare_evidence(
    repo_root: Path,
    *,
    preregistration_path: Path,
    implementation_commit: str,
    test_results_path: Path,
    git_executable: str | None = None,
) -> dict[str, Any]:
    preregistration = _read_json(preregistration_path)
    if not verify_v18_1_preregistration(preregistration):
        raise ValueError("V18.1 preregistration is invalid")
    code_audit = audit_v18_1_code_freeze(
        repo_root=repo_root,
        implementation_commit=implementation_commit,
        git_executable=git_executable,
    )
    preregistration_audit = audit_v18_1_preregistration_freeze(
        repo_root=repo_root,
        preregistration_path=preregistration_path,
        git_executable=git_executable,
        require_v18_1_tag=False,
    )
    if code_audit.get("status") != "passed":
        raise RuntimeError(f"blocked_remote_code_freeze:{code_audit['blockers']}")
    if preregistration_audit.get("status") != "passed":
        raise RuntimeError(
            "blocked_remote_preregistration_freeze:"
            f"{preregistration_audit['blockers']}"
        )
    changed_files = _git(
        repo_root,
        "diff",
        "--name-only",
        f"{V18_CLOSEOUT_COMMIT}..HEAD",
        git_executable=git_executable,
    ).splitlines()
    test_results = _read_json(test_results_path)
    required = (
        "realSignalBranchFixturePassed",
        "syntheticSecondCandidatePassed",
        "candidateNeutralImportPassed",
        "undefinedNameCheckPassed",
    )
    if any(test_results.get(key) is not True for key in required):
        raise RuntimeError("pre_result_test_gate_failed")
    prepared = prepare_v18_1_pre_result_artifacts(
        source_repo_root=repo_root,
        output_repo_root=repo_root,
        preregistration=preregistration,
        implementation_commit=implementation_commit,
        code_freeze_audit=code_audit,
        preregistration_freeze_audit=preregistration_audit,
        changed_files=changed_files,
        test_results=test_results,
    )
    return {
        "stage": "pre_result_evidence_created",
        "campaignId": preregistration["campaignId"],
        "candidateRoot": prepared["candidateRoot"].relative_to(repo_root).as_posix(),
        "codeFreezeStatus": code_audit["status"],
        "preregistrationFreezeStatus": preregistration_audit["status"],
        "candidateAdapterContractVersion": V18_1_ADAPTER_CONTRACT_VERSION,
        "formalRunClaimCount": 0,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
    }


def prepare_authorization(
    repo_root: Path,
    *,
    preregistration_path: Path,
    remote_verified_at: str,
    git_executable: str | None = None,
) -> dict[str, Any]:
    preregistration = _read_json(preregistration_path)
    if not verify_v18_1_preregistration(preregistration):
        raise ValueError("V18.1 preregistration is invalid")
    freeze = audit_v18_1_preregistration_freeze(
        repo_root=repo_root,
        preregistration_path=preregistration_path,
        git_executable=git_executable,
    )
    if freeze.get("status") != "passed":
        raise RuntimeError(f"blocked_remote_freeze:{freeze['blockers']}")
    tag_commit = str(freeze.get("remoteTags", {}).get(V18_1_TAG) or "")
    if len(tag_commit) != 40:
        raise RuntimeError("V18.1 freeze tag is unavailable")
    implementation_commit = str(preregistration["correctionImplementationCommit"])
    identity = build_v18_1_future_locked_oos_identity(
        preregistration,
        remote_freeze_commit=tag_commit,
        remote_verified_at=remote_verified_at,
    )
    _, _, future_audit = write_v18_1_future_locked_oos_metadata(
        identity,
        repo_root=repo_root,
    )
    leaf = _candidate_root(repo_root, preregistration)
    predecessor_audit = _read_json(
        leaf / "predecessor_v18_artifact_hash_audit.json"
    )
    fixture = _read_json(leaf / "signal_identity_golden_parity.json")
    checks = {
        "oldV18ArtifactsModified": predecessor_audit.get("changedArtifactCount") != 0,
        "oldV18LedgerModified": predecessor_audit.get("changedArtifactCount") != 0,
        "realSignalBranchFixturePassed": fixture.get("realSignalBranchFixturePassed") is True,
        "syntheticSecondCandidatePassed": fixture.get("syntheticSecondCandidatePassed") is True,
        "candidateNeutralImportPassed": fixture.get("candidateNeutralImportPassed") is True,
        "undefinedNameCheckPassed": fixture.get("undefinedNameCheckPassed") is True,
        "correctionCodePushed": True,
        "correctionPreregistrationPushed": True,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
    }
    authorization = build_v18_1_formal_run_authorization(
        preregistration,
        implementation_commit=implementation_commit,
        remote_implementation_commit=implementation_commit,
        remote_preregistration_commit=str(freeze["upstreamCommit"]),
        future_locked_oos_identity=identity,
        checks=checks,
    )
    if authorization.get("authorizationStatus") != "authorized":
        raise RuntimeError(
            f"formal_run_authorization_blocked:{authorization['blockers']}"
        )
    branch = _git(
        repo_root,
        "branch",
        "--show-current",
        git_executable=git_executable,
    )
    finalize_v18_1_pre_result_artifacts(
        candidate_root=leaf,
        preregistration=preregistration,
        future_locked_oos_identity=identity,
        future_locked_oos_audit=future_audit,
        authorization=authorization,
        preregistration_commit=str(freeze["upstreamCommit"]),
        freeze_commit=tag_commit,
        branch=branch,
    )
    return {
        "stage": "one_shot_authorization_created",
        "campaignId": preregistration["campaignId"],
        "futureLockedOosId": identity["futureLockedOosId"],
        "futureLockedOosStart": identity["startInclusive"],
        "authorizationHash": authorization["authorizationHash"],
        "formalRunClaimBudget": 1,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("preregister", "evidence", "authorize"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--preregistration", type=Path)
    parser.add_argument("--implementation-commit")
    parser.add_argument("--frozen-at", default=None)
    parser.add_argument("--test-results", type=Path)
    parser.add_argument("--remote-verified-at", default=None)
    parser.add_argument("--git-executable")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    preregistration_path = args.preregistration

    if args.stage == "preregister":
        if not args.implementation_commit:
            parser.error("--implementation-commit is required")
        result = prepare_preregistration(
            repo_root,
            implementation_commit=args.implementation_commit,
            frozen_at=args.frozen_at or _utc_now(),
        )
    else:
        if preregistration_path is None:
            parser.error("--preregistration is required")
        preregistration_path = preregistration_path.resolve()
        if args.stage == "evidence":
            if not args.implementation_commit or args.test_results is None:
                parser.error("--implementation-commit and --test-results are required")
            result = prepare_evidence(
                repo_root,
                preregistration_path=preregistration_path,
                implementation_commit=args.implementation_commit,
                test_results_path=args.test_results.resolve(),
                git_executable=args.git_executable,
            )
        else:
            result = prepare_authorization(
                repo_root,
                preregistration_path=preregistration_path,
                remote_verified_at=args.remote_verified_at or _utc_now(),
                git_executable=args.git_executable,
            )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
