"""Run the V18.2 evidence-chain correction inside the exact formal runtime."""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.formal_validation.freqtrade_runtime_loader import (
    EXACT_RUNTIME_VERSIONS,
)
from alphapilot.formal_validation.s01_dual_engine_audit import _load_strategy
from alphapilot.formal_validation.v18_2_contracts import (
    verify_v18_2_formal_run_authorization,
    verify_v18_2_preregistration,
)
from alphapilot.scripts.run_formal_walk_forward import (
    formal_artifact_root,
    run as run_generic,
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


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


def assert_exact_inprocess_runtime(*, repo_root: Path) -> None:
    """Prove the running interpreter is the digest-pinned Freqtrade environment."""

    try:
        import ccxt
        import freqtrade
        import numpy
        import pandas
        import pyarrow

        observed = _observed_runtime_versions(
            freqtrade=freqtrade,
            ccxt=ccxt,
            pandas=pandas,
            numpy=numpy,
            pyarrow=pyarrow,
        )
        mismatch = {
            key: {"expected": expected, "actual": observed.get(key)}
            for key, expected in EXACT_RUNTIME_VERSIONS.items()
            if observed.get(key) != expected
        }
        if mismatch:
            raise RuntimeError(f"runtime_version_mismatch:{mismatch}")
        _, strategy = _load_strategy(Path(repo_root).resolve())
        base_module = type(strategy).__mro__[1].__module__
        if not str(base_module).startswith("freqtrade."):
            raise RuntimeError("strategy_not_loaded_by_freqtrade")
    except Exception as error:
        if str(error).startswith("blocked_freqtrade_runtime"):
            raise
        raise RuntimeError(
            f"blocked_freqtrade_runtime:{type(error).__name__}:{error}"
        ) from error


def _frozen_auditor(
    *,
    freeze_audit_path: Path,
    preregistration: Mapping[str, Any],
    authorization: Mapping[str, Any],
):
    def audit(**_: object) -> dict[str, Any]:
        frozen = _read_json(freeze_audit_path)
        blockers = list(frozen.get("blockers") or [])
        if frozen.get("status") != "passed":
            blockers.append("remote_freeze_audit_not_passed")
        if frozen.get("preregistrationHash") != preregistration.get(
            "preregistrationHash"
        ):
            blockers.append("preregistration_hash_mismatch")
        if frozen.get("headCommit") != authorization.get(
            "remotePreregistrationCommit"
        ):
            blockers.append("remote_preregistration_commit_mismatch")
        return {
            **frozen,
            "status": "blocked" if blockers else "passed",
            "route": "blocked_remote_freeze" if blockers else "remote_freeze_verified",
            "blockers": sorted(set(blockers)),
        }

    return audit


def _write_accounting(destination: Path, *, result_generated: bool) -> None:
    attempt = {
        "schemaVersion": "s01_v18_2_operational_attempt_ledger_v1",
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
            "schemaVersion": "s01_v18_2_result_exposure_ledger_v1",
            "resultReadCount": attempt["resultReadCount"],
            "lockedOosAccessCount": 0,
            "formalEvidenceCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
    )


def run(
    repo_root: Path,
    *,
    preregistration_path: Path,
    candidate_id: str,
    authorization_path: Path,
    freeze_audit_path: Path,
    runtime_binding_path: Path,
    certification_path: Path,
    output_root: Path,
    data_root: Path,
) -> dict[str, Any]:
    """Run once; the command must itself be inside the pinned Docker runtime."""

    root = Path(repo_root).resolve()
    preregistration = _read_json(Path(preregistration_path).resolve())
    if not verify_v18_2_preregistration(preregistration):
        raise ValueError("V18.2 preregistration is invalid")
    assert_exact_inprocess_runtime(repo_root=root)
    authorization = _read_json(Path(authorization_path).resolve())
    runtime_binding = _read_json(Path(runtime_binding_path).resolve())
    certification = _read_json(Path(certification_path).resolve())
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
                preregistration_validator=verify_v18_2_preregistration,
                freeze_auditor=_frozen_auditor(
                    freeze_audit_path=Path(freeze_audit_path).resolve(),
                    preregistration=preregistration,
                    authorization=authorization,
                ),
                authorization_path=authorization_path,
                authorization_validator=lambda supplied, frozen: (
                    verify_v18_2_formal_run_authorization(
                        supplied, preregistration=frozen
                    )
                ),
                executor_context={
                    "formal_evidence_chain": {
                        "enabled": True,
                        "runtimeBinding": runtime_binding,
                        "certification": certification,
                    }
                },
                run_id=f"{candidate_id}-v18-2-formal-001",
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
    parser.add_argument("--certification", type=Path, required=True)
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
        certification_path=args.certification,
        output_root=args.output_root,
        data_root=args.data_root,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
