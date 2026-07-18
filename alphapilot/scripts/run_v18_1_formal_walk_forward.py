"""Run the remotely frozen V18.1 correction exactly once."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.formal_validation.v18_1_contracts import (
    verify_v18_1_formal_run_authorization,
    verify_v18_1_preregistration,
)
from alphapilot.formal_validation.v18_1_remote_freeze import (
    audit_v18_1_preregistration_freeze,
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


def _write_accounting(
    destination: Path,
    *,
    result_generated: bool,
    failure_reason: str | None = None,
) -> None:
    attempt = {
        "schemaVersion": "s01_v18_1_operational_attempt_ledger_v1",
        "operationalAttemptCount": 1,
        "formalRunClaimCount": 1,
        "formalRunAttemptCount": 1,
        "formalResultRunCount": 1 if result_generated else 0,
        "trialClassification": (
            "formal_result_generated"
            if result_generated
            else "implementation_failed_before_result"
        ),
        "resultExposed": result_generated,
        "selectionInformationGained": result_generated,
        "validComparableTrial": result_generated,
        "failureReason": failure_reason,
    }
    exposure = {
        "schemaVersion": "s01_v18_1_result_exposure_ledger_v1",
        "formalResultRunCount": 1 if result_generated else 0,
        "resultReadCount": 1 if result_generated else 0,
        "resultReadTrialCount": 1 if result_generated else 0,
        "formalResultArtifactCount": 1 if result_generated else 0,
        "resultExposed": result_generated,
        "statisticalCandidateCount": 1 if result_generated else 0,
        "benjaminiHochbergPanelCount": 0,
        "pboPanelCount": 0,
        "spaPanelCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    write_json_atomic(destination / "operational_attempt_ledger.json", attempt)
    write_json_atomic(destination / "result_exposure_ledger.json", exposure)


def run(
    repo_root: Path,
    *,
    preregistration_path: Path,
    candidate_id: str,
    authorization_path: Path,
    output_root: Path,
    data_root: Path | None = None,
    git_executable: str | None = None,
) -> dict[str, Any]:
    """Execute V18.1 through the candidate-neutral generic runner."""

    preregistration = _read_json(Path(preregistration_path).resolve())
    campaign_id = str(preregistration.get("campaignId") or "")
    destination = formal_artifact_root(
        output_root,
        campaign_id=campaign_id,
        candidate_id=candidate_id,
    )
    try:
        route = dict(
            run_generic(
                repo_root,
                preregistration_path=preregistration_path,
                candidate_id=candidate_id,
                output_root=output_root,
                data_root=data_root,
                git_executable=git_executable,
                preregistration_validator=verify_v18_1_preregistration,
                freeze_auditor=audit_v18_1_preregistration_freeze,
                authorization_path=authorization_path,
                authorization_validator=lambda authorization, frozen: (
                    verify_v18_1_formal_run_authorization(
                        authorization, preregistration=frozen
                    )
                ),
                run_id=f"{candidate_id}-v18-1-formal-001",
            )
        )
    except Exception as error:
        if (destination / "formal_run_ledger.json").is_file():
            _write_accounting(
                destination,
                result_generated=False,
                failure_reason=type(error).__name__,
            )
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
            }
        )
        write_json_atomic(destination / "formal_run_route.json", route)
    return route


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--git-executable")
    args = parser.parse_args(argv)
    route = run(
        args.repo_root,
        preregistration_path=args.preregistration,
        candidate_id=args.candidate_id,
        authorization_path=args.authorization,
        output_root=args.output_root,
        data_root=args.data_root,
        git_executable=args.git_executable,
    )
    print(json.dumps(route, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
