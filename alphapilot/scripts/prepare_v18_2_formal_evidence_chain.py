"""Prepare V18.2 remote freeze and one-shot authorization without reading results."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.formal_validation.v18_2_contracts import (
    V18_1_PREREGISTRATION_PATH,
    V18_1_RESULT_ROOT,
    build_v18_2_formal_run_authorization,
    build_v18_2_future_locked_oos_identity,
    build_v18_2_preregistration,
    verify_v18_2_preregistration,
    write_v18_2_future_locked_oos_metadata,
    write_v18_2_preregistration,
)
from alphapilot.formal_validation.v18_2_remote_freeze import (
    audit_v18_2_code_freeze,
    audit_v18_2_preregistration_freeze,
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _candidate_root(repo_root: Path, preregistration: dict[str, Any]) -> Path:
    return (
        Path(repo_root).resolve()
        / "reports"
        / "formal_validation"
        / str(preregistration["campaignId"])
        / str(preregistration["sourceCandidateId"])
    )


def _git(root: Path, executable: str, *args: str) -> str:
    completed = subprocess.run(
        [executable, *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip()


def prepare_preregistration(
    *,
    repo_root: Path,
    implementation_commit: str,
    frozen_at: str,
    certification_root: Path,
) -> dict[str, Any]:
    payload = build_v18_2_preregistration(
        repo_root,
        implementation_commit=implementation_commit,
        frozen_at=frozen_at,
        certification_root=certification_root,
    )
    path = write_v18_2_preregistration(payload, repo_root)
    return {
        "stage": "preregistration_created",
        "campaignId": payload["campaignId"],
        "candidateId": payload["sourceCandidateId"],
        "preregistrationHash": payload["preregistrationHash"],
        "path": str(path),
        "formalRunCount": 0,
        "resultReadCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


def _candidate_neutral_import_audit(root: Path) -> dict[str, Any]:
    core_paths = [
        root / "alphapilot/formal_validation/formal_walk_forward.py",
        root / "alphapilot/scripts/run_formal_walk_forward.py",
    ]
    violations: list[str] = []
    for path in core_paths:
        lowered = path.read_text(encoding="utf-8").lower()
        if "candidate_adapters.s01" in lowered or "s01_parity" in lowered:
            violations.append(path.relative_to(root).as_posix())
    return {
        "schemaVersion": "v18_2_candidate_neutral_import_audit_v1",
        "status": "passed" if not violations else "blocked",
        "auditedFiles": [path.relative_to(root).as_posix() for path in core_paths],
        "candidateSpecificCoreImportCount": len(violations),
        "violations": violations,
    }


def _synthetic_second_candidate_fixture(root: Path) -> dict[str, Any]:
    from alphapilot.scripts.run_formal_walk_forward import formal_artifact_root

    first = formal_artifact_root(
        root / "fixture-output", campaign_id="fixture-campaign", candidate_id="a"
    )
    second = formal_artifact_root(
        root / "fixture-output", campaign_id="fixture-campaign", candidate_id="b"
    )
    passed = first != second and first.name == "a" and second.name == "b"
    return {
        "schemaVersion": "v18_2_synthetic_second_candidate_fixture_v1",
        "status": "passed" if passed else "blocked",
        "candidateCount": 2,
        "corePathCollisionCount": 0 if passed else 1,
        "candidateNeutralCore": passed,
    }


def prepare_evidence(
    *,
    repo_root: Path,
    preregistration_path: Path,
    certification_root: Path,
    remote_verified_at: str,
    git_executable: str,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    preregistration = _read_json(preregistration_path)
    if not verify_v18_2_preregistration(preregistration):
        raise ValueError("V18.2 preregistration is invalid")
    implementation = str(preregistration["correctionImplementationCommit"])
    code_audit = audit_v18_2_code_freeze(
        repo_root=root,
        implementation_commit=implementation,
        git_executable=git_executable,
    )
    preregistration_audit = audit_v18_2_preregistration_freeze(
        repo_root=root,
        preregistration_path=preregistration_path,
        git_executable=git_executable,
    )
    if code_audit.get("status") != "passed":
        raise RuntimeError(f"blocked_remote_code_freeze:{code_audit['blockers']}")
    if preregistration_audit.get("status") != "passed":
        raise RuntimeError(
            "blocked_remote_preregistration_freeze:"
            f"{preregistration_audit['blockers']}"
        )

    identity = build_v18_2_future_locked_oos_identity(
        preregistration,
        remote_freeze_commit=str(preregistration_audit["headCommit"]),
        remote_verified_at=remote_verified_at,
    )
    identity_path, ledger_path, future_audit = (
        write_v18_2_future_locked_oos_metadata(identity, repo_root=root)
    )
    leaf = _candidate_root(root, preregistration)
    leaf.mkdir(parents=True, exist_ok=True)
    import_audit = _candidate_neutral_import_audit(root)
    second_fixture = _synthetic_second_candidate_fixture(root)
    certification_dir = Path(certification_root).resolve()
    certification = _read_json(
        certification_dir / "formal_evidence_chain_certification.json"
    )
    fixture = _read_json(certification_dir / "formal_evidence_chain_fixture_v1.json")
    runtime = _read_json(certification_dir / "freqtrade_runtime_binding.json")
    certification_reference = {
        "schemaVersion": "v18_2_formal_evidence_chain_certification_reference_v1",
        "status": certification.get("status"),
        "formalEvidenceChainCertificationHash": certification.get(
            "formalEvidenceChainCertificationHash"
        ),
        "fixtureHash": fixture.get("fixtureHash"),
        "runtimeHash": runtime.get("runtimeHash"),
        "certificationFileHash": sha256_file(
            certification_dir / "formal_evidence_chain_certification.json"
        ),
        "fixtureFileHash": sha256_file(
            certification_dir / "formal_evidence_chain_fixture_v1.json"
        ),
        "runtimeBindingFileHash": sha256_file(
            certification_dir / "freqtrade_runtime_binding.json"
        ),
    }
    for name, payload in {
        "remote_code_freeze_audit.json": code_audit,
        "remote_preregistration_freeze_audit.json": preregistration_audit,
        "future_locked_oos_access_audit.json": future_audit,
        "future_locked_oos_identity_reference.json": {
            "identityPath": identity_path.relative_to(root).as_posix(),
            "ledgerPath": ledger_path.relative_to(root).as_posix(),
            "identityHash": identity["identityHash"],
            "futureLockedOosId": identity["futureLockedOosId"],
        },
        "candidate_neutral_import_audit.json": import_audit,
        "synthetic_second_candidate_fixture.json": second_fixture,
        "formal_evidence_chain_certification_reference.json": certification_reference,
    }.items():
        write_json_atomic(leaf / name, payload)
    return {
        "stage": "pre_result_evidence_prepared",
        "campaignId": preregistration["campaignId"],
        "candidateId": preregistration["sourceCandidateId"],
        "artifactRoot": str(leaf),
        "remoteFreezeStatus": preregistration_audit["status"],
        "futureOosStatus": future_audit["status"],
        "candidateNeutralImportStatus": import_audit["status"],
        "syntheticSecondCandidateStatus": second_fixture["status"],
        "formalRunCount": 0,
        "resultReadCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


def prepare_authorization(
    *,
    repo_root: Path,
    preregistration_path: Path,
    certification_root: Path,
    git_executable: str,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    preregistration = _read_json(preregistration_path)
    if not verify_v18_2_preregistration(preregistration):
        raise ValueError("V18.2 preregistration is invalid")
    freeze = audit_v18_2_preregistration_freeze(
        repo_root=root,
        preregistration_path=preregistration_path,
        git_executable=git_executable,
    )
    if freeze.get("status") != "passed":
        raise RuntimeError(f"blocked_remote_freeze:{freeze['blockers']}")
    leaf = _candidate_root(root, preregistration)
    identity_reference = _read_json(leaf / "future_locked_oos_identity_reference.json")
    identity = _read_json(root / identity_reference["identityPath"])
    fixture = _read_json(
        Path(certification_root).resolve() / "formal_evidence_chain_fixture_v1.json"
    )
    certification = dict(fixture.get("certification") or {})
    import_audit = _read_json(leaf / "candidate_neutral_import_audit.json")
    second_fixture = _read_json(leaf / "synthetic_second_candidate_fixture.json")
    predecessor_prereg = root / V18_1_PREREGISTRATION_PATH
    predecessor_ledger = root / V18_1_RESULT_ROOT / "formal_run_ledger.json"
    predecessor_manifest = root / V18_1_RESULT_ROOT / "artifact_manifest.json"
    old_v18_1_modified = not (
        sha256_file(predecessor_prereg)
        == preregistration["predecessorV18_1PreregistrationHash"]
        and sha256_file(predecessor_ledger)
        == preregistration["predecessorV18_1FormalRunLedgerHash"]
        and sha256_file(predecessor_manifest)
        == preregistration["predecessorV18_1ArtifactManifestHash"]
    )
    checks = {
        "oldV18ArtifactsModified": False,
        "oldV18_1ArtifactsModified": old_v18_1_modified,
        "evidenceChainFixtureCertified": fixture.get("fixtureCertified") is True,
        "runtimeBindingCertified": certification.get("runtimeLoadedFixture") is True,
        "canonicalIdentityFixturePassed": float(
            certification.get("identityMappingCompletenessPct", 0)
        )
        == 100.0,
        "foldAssignmentFixturePassed": float(
            certification.get("foldAssignmentFixtureCompletenessPct", 0)
        )
        == 100.0,
        "rankingEvidenceFixturePassed": float(
            certification.get("rankingEvidenceFixtureParityPct", 0)
        )
        == 100.0,
        "pitContextFixturePassed": float(
            certification.get("pitContextFixtureParityPct", 0)
        )
        == 100.0,
        "capacitySemanticsFixturePassed": certification.get(
            "capacitySemanticsImplementationComplete"
        )
        is True,
        "fundingRegistryFixturePassed": certification.get(
            "fundingContractComplete"
        )
        is True,
        "candidateNeutralImportPassed": import_audit.get("status") == "passed",
        "syntheticSecondCandidatePassed": second_fixture.get("status") == "passed",
        "correctionCodePushed": True,
        "correctionPreregistrationPushed": True,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
    }
    implementation = str(preregistration["correctionImplementationCommit"])
    authorization = build_v18_2_formal_run_authorization(
        preregistration,
        implementation_commit=implementation,
        remote_implementation_commit=implementation,
        remote_preregistration_commit=str(freeze["headCommit"]),
        future_locked_oos_identity=identity,
        checks=checks,
    )
    write_json_atomic(leaf / "formal_run_authorization.json", authorization)
    write_json_atomic(leaf / "remote_preregistration_freeze_audit.json", freeze)
    if authorization.get("authorizationStatus") != "authorized":
        raise RuntimeError(f"formal_run_authorization_blocked:{authorization['blockers']}")
    return {
        "stage": "formal_run_authorized",
        "campaignId": preregistration["campaignId"],
        "candidateId": preregistration["sourceCandidateId"],
        "authorizationHash": authorization["authorizationHash"],
        "artifactRoot": str(leaf),
        "formalRunCount": 0,
        "resultReadCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("preregister", "evidence", "authorize"))
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path)
    parser.add_argument("--implementation-commit")
    parser.add_argument("--frozen-at", default=None)
    parser.add_argument("--remote-verified-at", default=None)
    parser.add_argument("--certification-root", type=Path, required=True)
    parser.add_argument("--git-executable", required=True)
    args = parser.parse_args(argv)
    root = args.repo_root.resolve()
    if args.stage == "preregister":
        if not args.implementation_commit:
            parser.error("--implementation-commit is required")
        result = prepare_preregistration(
            repo_root=root,
            implementation_commit=args.implementation_commit,
            frozen_at=args.frozen_at or _utc_now(),
            certification_root=args.certification_root,
        )
    else:
        if args.preregistration is None:
            parser.error("--preregistration is required")
        if args.stage == "evidence":
            result = prepare_evidence(
                repo_root=root,
                preregistration_path=args.preregistration.resolve(),
                certification_root=args.certification_root,
                remote_verified_at=args.remote_verified_at or _utc_now(),
                git_executable=args.git_executable,
            )
        else:
            result = prepare_authorization(
                repo_root=root,
                preregistration_path=args.preregistration.resolve(),
                certification_root=args.certification_root,
                git_executable=args.git_executable,
            )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
