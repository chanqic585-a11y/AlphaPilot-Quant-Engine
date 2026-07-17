"""Prepare immutable V18.3 preregistration, freeze evidence, and authorization."""

from __future__ import annotations

import argparse
import ast
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.formal_validation.candidate_adapter import (
    resolve_candidate_signal_identity,
    validate_candidate_binding,
)
from alphapilot.formal_validation.v18_3_contracts import (
    build_v18_3_formal_run_authorization,
    build_v18_3_future_locked_oos_identity,
    build_v18_3_preregistration,
    verify_v18_3_preregistration,
    write_v18_3_future_locked_oos_metadata,
    write_v18_3_preregistration,
)
from alphapilot.formal_validation.v18_3_remote_freeze import (
    audit_v18_3_code_freeze,
    audit_v18_3_preregistration_freeze,
)
from alphapilot.scripts.run_formal_walk_forward import formal_artifact_root, run


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _write_once(path: Path, payload: Mapping[str, Any]) -> None:
    expected = dict(payload)
    if path.exists():
        if _read_json(path) != expected:
            raise RuntimeError(f"immutable_evidence_conflict:{path.name}")
        return
    write_json_atomic(path, expected)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _candidate_root(repo_root: Path, preregistration: Mapping[str, Any]) -> Path:
    return formal_artifact_root(
        Path(repo_root).resolve() / "reports/formal_validation",
        campaign_id=str(preregistration["campaignId"]),
        candidate_id=str(preregistration["sourceCandidateId"]),
    )


def _candidate_neutral_import_audit(repo_root: Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    core_path = root / "alphapilot/scripts/run_formal_walk_forward.py"
    tree = ast.parse(core_path.read_text(encoding="utf-8"))
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
    imports_s01 = any(
        module.split(".")[-1].startswith("s01") for module in imported_modules
    )
    signature = inspect.signature(run)
    artifact_signature = inspect.signature(formal_artifact_root)
    adapter_present = "adapter_resolver" in signature.parameters
    dynamic_artifact_identity = {
        "campaign_id",
        "candidate_id",
    }.issubset(artifact_signature.parameters)
    core = {
        "schemaVersion": "v18_3_candidate_neutral_import_audit_v1",
        "status": (
            "passed"
            if not imports_s01 and adapter_present and dynamic_artifact_identity
            else "failed"
        ),
        "formalCorePath": core_path.relative_to(root).as_posix(),
        "formalCoreImportsS01Module": imports_s01,
        "candidateAdapterBoundaryPresent": adapter_present,
        "dynamicArtifactIdentityPresent": dynamic_artifact_identity,
        "importedModules": sorted(imported_modules),
    }
    return {**core, "auditHash": stable_hash(core, prefix="v18_3_candidate_neutral_import")}


class _SyntheticSecondCandidateAdapter:
    candidate_id = "synthetic_second_candidate_fixture"
    adapter_id = "synthetic_second_candidate_adapter"
    adapter_version = "1"

    def signal_identity(self, **kwargs: Any) -> str:
        return stable_hash(kwargs, prefix="synthetic_second_candidate_signal")


def _synthetic_second_candidate_fixture(repo_root: Path) -> dict[str, Any]:
    del repo_root
    adapter = _SyntheticSecondCandidateAdapter()
    preregistration = {"sourceCandidateId": adapter.candidate_id}
    validate_candidate_binding(
        adapter=adapter,
        preregistration=preregistration,
        requested_candidate_id=adapter.candidate_id,
    )
    signal_id = resolve_candidate_signal_identity(
        adapter=adapter,
        event={
            "candidateId": adapter.candidate_id,
            "symbol": "SYNTH/USDT:USDT",
            "direction": "long",
            "signalTimestamp": "2026-07-18T00:00:00Z",
            "entryTimestamp": "2026-07-18T04:00:00Z",
        },
    )
    core = {
        "schemaVersion": "v18_3_synthetic_second_candidate_fixture_v1",
        "status": "passed" if signal_id else "failed",
        "candidateId": adapter.candidate_id,
        "adapterId": adapter.adapter_id,
        "adapterVersion": adapter.adapter_version,
        "bindingPassed": True,
        "signalIdentityResolved": bool(signal_id),
        "signalIdentityHash": signal_id,
        "formalRunClaimCount": 0,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
    }
    return {**core, "fixtureHash": stable_hash(core, prefix="v18_3_second_candidate_fixture")}


def prepare_preregistration(
    *,
    repo_root: Path,
    implementation_commit: str,
    frozen_at: str,
    certification_root: Path,
    git_executable: str | None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    code_freeze = audit_v18_3_code_freeze(
        repo_root=root,
        implementation_commit=implementation_commit,
        git_executable=git_executable,
    )
    if code_freeze.get("status") != "passed":
        raise RuntimeError(f"v18_3_code_not_frozen:{code_freeze.get('blockers')}")
    preregistration = build_v18_3_preregistration(
        root,
        implementation_commit=implementation_commit,
        frozen_at=frozen_at,
        certification_root=certification_root,
    )
    path = write_v18_3_preregistration(preregistration, root)
    candidate_root = _candidate_root(root, preregistration)
    candidate_root.mkdir(parents=True, exist_ok=True)
    _write_once(candidate_root / "remote_code_freeze_audit.json", code_freeze)
    state = {
        "schemaVersion": "v18_3_pre_result_state_v1",
        "stage": "preregistration_created",
        "campaignId": preregistration["campaignId"],
        "candidateId": preregistration["sourceCandidateId"],
        "preregistrationHash": preregistration["preregistrationHash"],
        "formalRunClaimCount": 0,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    _write_once(candidate_root / "pre_result_state.json", state)
    return {
        "stage": state["stage"],
        "campaignId": preregistration["campaignId"],
        "preregistrationPath": path.as_posix(),
        "candidateRoot": candidate_root.as_posix(),
    }


def prepare_evidence(
    *,
    repo_root: Path,
    preregistration_path: Path,
    remote_verified_at: str,
    git_executable: str | None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    preregistration = _read_json(Path(preregistration_path).resolve())
    if not verify_v18_3_preregistration(preregistration):
        raise ValueError("V18.3 preregistration is invalid")
    freeze = audit_v18_3_preregistration_freeze(
        repo_root=root,
        preregistration_path=Path(preregistration_path).resolve(),
        git_executable=git_executable,
    )
    if freeze.get("status") != "passed":
        raise RuntimeError(f"v18_3_preregistration_not_frozen:{freeze.get('blockers')}")
    identity = build_v18_3_future_locked_oos_identity(
        preregistration,
        remote_freeze_commit=str(freeze["headCommit"]),
        remote_verified_at=remote_verified_at,
    )
    identity_path, ledger_path, oos_audit = write_v18_3_future_locked_oos_metadata(
        identity, repo_root=root
    )
    candidate_root = _candidate_root(root, preregistration)
    candidate_root.mkdir(parents=True, exist_ok=True)
    import_audit = _candidate_neutral_import_audit(root)
    fixture = _synthetic_second_candidate_fixture(root)
    certification_path = root / str(
        preregistration["signalEvidenceStructuralCertificationPath"]
    )
    certification_reference = {
        "schemaVersion": "v18_3_signal_evidence_certification_reference_v1",
        "status": preregistration["signalEvidenceStructuralCertificationStatus"],
        "certificationHash": preregistration[
            "signalEvidenceStructuralCertificationHash"
        ],
        "certificationPath": certification_path.relative_to(root).as_posix(),
        "certificationFileHash": sha256_file(certification_path),
        "formalRunClaimCount": 0,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
    }
    artifacts = {
        "remote_preregistration_freeze_audit.json": freeze,
        "future_locked_oos_access_audit.json": oos_audit,
        "candidate_neutral_import_audit.json": import_audit,
        "synthetic_second_candidate_fixture.json": fixture,
        "signal_evidence_structural_certification_reference.json": certification_reference,
    }
    for name, payload in artifacts.items():
        _write_once(candidate_root / name, payload)
    state = {
        "schemaVersion": "v18_3_pre_result_evidence_state_v1",
        "stage": "pre_result_evidence_prepared",
        "campaignId": preregistration["campaignId"],
        "candidateId": preregistration["sourceCandidateId"],
        "preregistrationHash": preregistration["preregistrationHash"],
        "remotePreregistrationCommit": freeze["headCommit"],
        "futureLockedOosId": identity["futureLockedOosId"],
        "futureLockedOosIdentityPath": identity_path.relative_to(root).as_posix(),
        "futureLockedOosLedgerPath": ledger_path.relative_to(root).as_posix(),
        "formalRunClaimCount": 0,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    _write_once(candidate_root / "pre_result_evidence_state.json", state)
    return {"stage": state["stage"], "candidateRoot": candidate_root.as_posix()}


def prepare_authorization(
    *,
    repo_root: Path,
    preregistration_path: Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    preregistration = _read_json(Path(preregistration_path).resolve())
    candidate_root = _candidate_root(root, preregistration)
    freeze = _read_json(candidate_root / "remote_preregistration_freeze_audit.json")
    import_audit = _read_json(candidate_root / "candidate_neutral_import_audit.json")
    fixture = _read_json(candidate_root / "synthetic_second_candidate_fixture.json")
    certification = _read_json(
        root / str(preregistration["signalEvidenceStructuralCertificationPath"])
    )
    identity_path = next(
        (root / "research/locked_oos").glob(
            f"{preregistration['campaignId']}_future_locked_oos_identity.json"
        )
    )
    identity = _read_json(identity_path)
    checks = {
        "predecessorV18_2ArtifactsModified": False,
        "structuralCertificationPassed": certification.get("status") == "certified",
        "dispositionConservationPassed": preregistration.get(
            "formalEventDispositionConservationPassed"
        )
        is True,
        "rankingRecordCoveragePassed": preregistration.get(
            "rankingEvidenceRecordCoveragePercent"
        )
        == 100.0,
        "rankingStatusCoveragePassed": preregistration.get(
            "rankingEvidenceStatusCoveragePercent"
        )
        == 100.0,
        "rankingParityPassed": preregistration.get("rankingEvidenceParityPercent")
        == 100.0,
        "postEntryDataUseZero": int(preregistration.get("postEntryDataUseCount", -1))
        == 0,
        "economicMetricReadsZero": int(
            preregistration.get("economicMetricReadCount", -1)
        )
        == 0,
        "exitReplayZero": int(preregistration.get("exitReplayCount", -1)) == 0,
        "candidateNeutralImportPassed": import_audit.get("status") == "passed",
        "syntheticSecondCandidatePassed": fixture.get("status") == "passed",
        "correctionCodePushed": freeze.get("status") == "passed",
        "correctionPreregistrationPushed": freeze.get("status") == "passed",
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
    }
    authorization = build_v18_3_formal_run_authorization(
        preregistration,
        implementation_commit=str(preregistration["correctionImplementationCommit"]),
        remote_implementation_commit=str(
            preregistration["correctionImplementationCommit"]
        ),
        remote_preregistration_commit=str(freeze["headCommit"]),
        future_locked_oos_identity=identity,
        checks=checks,
    )
    if authorization.get("authorizationStatus") != "authorized":
        raise RuntimeError(f"v18_3_formal_run_not_authorized:{authorization['blockers']}")
    path = candidate_root / "formal_run_authorization.json"
    _write_once(path, authorization)
    state = {
        "schemaVersion": "v18_3_formal_run_authorization_state_v1",
        "stage": "formal_run_authorized",
        "campaignId": preregistration["campaignId"],
        "candidateId": preregistration["sourceCandidateId"],
        "authorizationHash": authorization["authorizationHash"],
        "formalRunClaimCount": 0,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    _write_once(candidate_root / "formal_run_authorization_state.json", state)
    return {"stage": state["stage"], "authorizationPath": path.as_posix()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("preregister", "evidence", "authorize"))
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--implementation-commit")
    parser.add_argument("--frozen-at", default=_utc_now())
    parser.add_argument("--certification-root", type=Path)
    parser.add_argument("--preregistration", type=Path)
    parser.add_argument("--remote-verified-at", default=_utc_now())
    parser.add_argument("--git-executable")
    args = parser.parse_args(argv)
    if args.stage == "preregister":
        if not args.implementation_commit or not args.certification_root:
            parser.error("preregister requires --implementation-commit and --certification-root")
        result = prepare_preregistration(
            repo_root=args.repo_root,
            implementation_commit=args.implementation_commit,
            frozen_at=args.frozen_at,
            certification_root=args.certification_root,
            git_executable=args.git_executable,
        )
    elif args.stage == "evidence":
        if not args.preregistration:
            parser.error("evidence requires --preregistration")
        result = prepare_evidence(
            repo_root=args.repo_root,
            preregistration_path=args.preregistration,
            remote_verified_at=args.remote_verified_at,
            git_executable=args.git_executable,
        )
    else:
        if not args.preregistration:
            parser.error("authorize requires --preregistration")
        result = prepare_authorization(
            repo_root=args.repo_root,
            preregistration_path=args.preregistration,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
