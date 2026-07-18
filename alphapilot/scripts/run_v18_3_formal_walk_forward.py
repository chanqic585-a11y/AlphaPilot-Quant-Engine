"""Run the one-shot V18.3 fold and ranking evidence correction."""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.formal_validation.v18_2_evidence_chain import (
    validate_evidence_chain_configuration,
)
from alphapilot.formal_validation.v18_3_contracts import (
    verify_v18_3_formal_run_authorization,
    verify_v18_3_preregistration,
)
from alphapilot.scripts.run_formal_walk_forward import (
    formal_artifact_root,
    run as run_generic,
)
from alphapilot.scripts.run_v18_2_formal_walk_forward import (
    _frozen_auditor,
    _read_json,
    assert_exact_inprocess_runtime,
)


def _observed_runtime_versions(
    *, freqtrade: Any, ccxt: Any, pandas: Any, numpy: Any, pyarrow: Any
) -> dict[str, str]:
    return {
        "pythonVersion": platform.python_version(),
        "freqtradeVersion": str(freqtrade.__version__),
        "ccxtVersion": str(ccxt.__version__),
        "pandasVersion": str(pandas.__version__),
        "numpyVersion": str(numpy.__version__),
        "pyarrowVersion": str(pyarrow.__version__),
    }


def _write_accounting(destination: Path, *, result_generated: bool) -> None:
    attempt = {
        "schemaVersion": "s01_v18_3_operational_attempt_ledger_v1",
        "formalRunClaimCount": 1,
        "formalRunAttemptCount": 1,
        "formalResultRunCount": 1 if result_generated else 0,
        "resultReadCount": 1 if result_generated else 0,
        "formalResultArtifactCount": 1 if result_generated else 0,
        "lockedOosAccessCount": 0,
        "formalEvidenceCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    write_json_atomic(destination / "operational_attempt_ledger.json", attempt)
    write_json_atomic(
        destination / "result_exposure_ledger.json",
        {
            "schemaVersion": "s01_v18_3_result_exposure_ledger_v1",
            "resultReadCount": attempt["resultReadCount"],
            "lockedOosAccessCount": 0,
            "formalEvidenceCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
    )


def _validate_structural_certification(
    certification: dict[str, Any], *, preregistration: dict[str, Any]
) -> None:
    if certification.get("status") != "certified":
        raise RuntimeError("signal_evidence_structural_certification_not_certified")
    observed_hash = str(
        certification.get("signalEvidenceStructuralCertificationHash") or ""
    )
    expected_hash = str(
        preregistration.get("signalEvidenceStructuralCertificationHash") or ""
    )
    if not observed_hash or (expected_hash and observed_hash != expected_hash):
        raise RuntimeError("signal_evidence_structural_certification_hash_mismatch")
    required_true = (
        "economicResultComputationDisabled",
        "exitReplayDisabled",
        "resultMetricWriterDisabled",
    )
    required_zero = (
        "economicMetricReadCount",
        "exitReplayCount",
        "formalRunClaimCount",
        "formalRunAttemptCount",
        "resultReadCount",
        "lockedOosAccessCount",
        "formalEvidenceCount",
        "releaseCount",
        "orderCount",
    )
    if any(certification.get(field) is not True for field in required_true):
        raise RuntimeError("signal_evidence_structural_certification_guard_failed")
    if any(int(certification.get(field) or 0) != 0 for field in required_zero):
        raise RuntimeError("signal_evidence_structural_certification_scope_exceeded")


def run(
    repo_root: Path,
    *,
    preregistration_path: Path,
    candidate_id: str,
    authorization_path: Path,
    freeze_audit_path: Path,
    runtime_binding_path: Path,
    evidence_chain_certification_path: Path,
    structural_certification_path: Path,
    output_root: Path,
    data_root: Path,
) -> dict[str, Any]:
    """Run once inside the digest-pinned formal runtime."""

    root = Path(repo_root).resolve()
    preregistration = _read_json(Path(preregistration_path).resolve())
    if not verify_v18_3_preregistration(preregistration):
        raise ValueError("V18.3 preregistration is invalid")
    assert_exact_inprocess_runtime(repo_root=root)
    authorization = _read_json(Path(authorization_path).resolve())
    runtime_binding = _read_json(Path(runtime_binding_path).resolve())
    evidence_chain_certification = _read_json(
        Path(evidence_chain_certification_path).resolve()
    )
    structural_certification = _read_json(
        Path(structural_certification_path).resolve()
    )
    evidence_chain_context = {
        "enabled": True,
        "evidenceRecordVersion": "v18_3",
        "runtimeBinding": runtime_binding,
        "certification": evidence_chain_certification,
        "structuralCertification": structural_certification,
    }
    validate_evidence_chain_configuration(evidence_chain_context)
    _validate_structural_certification(
        structural_certification, preregistration=preregistration
    )
    destination = formal_artifact_root(
        output_root,
        campaign_id=str(preregistration["campaignId"]),
        candidate_id=candidate_id,
    )
    try:
        route = dict(
            run_generic(
                root,
                preregistration_path=preregistration_path,
                candidate_id=candidate_id,
                output_root=output_root,
                data_root=data_root,
                preregistration_validator=verify_v18_3_preregistration,
                freeze_auditor=_frozen_auditor(
                    freeze_audit_path=Path(freeze_audit_path).resolve(),
                    preregistration=preregistration,
                    authorization=authorization,
                ),
                authorization_path=authorization_path,
                authorization_validator=lambda supplied, frozen: (
                    verify_v18_3_formal_run_authorization(
                        supplied, preregistration=frozen
                    )
                ),
                executor_context={
                    "formal_evidence_chain": evidence_chain_context
                },
                run_id=f"{candidate_id}-v18-3-formal-001",
            )
        )
    except Exception:
        if (destination / "formal_run_ledger.json").is_file():
            _write_accounting(destination, result_generated=False)
        raise
    if int(route.get("formalRunCount", 0)) == 1:
        _write_accounting(destination, result_generated=True)
        route.update(
            {
                "formalRunClaimCount": 1,
                "formalRunAttemptCount": 1,
                "formalResultRunCount": 1,
                "resultReadCount": 1,
                "formalResultArtifactCount": 1,
                "formalEvidenceCount": 0,
                "releaseCount": 0,
                "demoArm": False,
                "orderCount": 0,
            }
        )
        write_json_atomic(destination / "formal_run_route.json", route)
    return route


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--freeze-audit", type=Path, required=True)
    parser.add_argument("--runtime-binding", type=Path, required=True)
    parser.add_argument(
        "--evidence-chain-certification", type=Path, required=True
    )
    parser.add_argument("--structural-certification", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run(
        args.repo_root,
        preregistration_path=args.preregistration,
        candidate_id=args.candidate_id,
        authorization_path=args.authorization,
        freeze_audit_path=args.freeze_audit,
        runtime_binding_path=args.runtime_binding,
        evidence_chain_certification_path=args.evidence_chain_certification,
        structural_certification_path=args.structural_certification,
        output_root=args.output_root,
        data_root=args.data_root,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
