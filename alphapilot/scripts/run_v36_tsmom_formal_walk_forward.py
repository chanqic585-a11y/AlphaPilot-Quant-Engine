"""Run one remotely frozen V36 TSMOM candidate through the generic core."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from alphapilot.formal_validation.v36_contracts import (
    verify_v36_formal_run_authorization,
    verify_v36_preregistration,
)
from alphapilot.formal_validation.v36_remote_freeze import audit_v36_remote_freeze
from alphapilot.scripts.run_formal_walk_forward import run as run_generic


def run(
    repo_root: Path,
    *,
    preregistration_path: Path,
    candidate_id: str,
    authorization_path: Path | None,
    output_root: Path,
    data_root: Path | None = None,
    git_executable: str | None = None,
    preregistration_validator: Callable[[Mapping[str, Any]], bool] = verify_v36_preregistration,
    freeze_auditor: Callable[..., Mapping[str, Any]] = audit_v36_remote_freeze,
    adapter_resolver: Callable[[str], Any] | None = None,
    input_loader: Callable[..., Any] | None = None,
    executor: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Fail closed before adapter resolution when authorization is absent."""

    effective_auditor = freeze_auditor
    if authorization_path is None:
        def effective_auditor(**kwargs: Any) -> Mapping[str, Any]:
            audit = dict(freeze_auditor(**kwargs))
            if audit.get("status") == "passed":
                audit.update(
                    {
                        "status": "blocked",
                        "route": "blocked_formal_run_authorization",
                        "blockers": ["formal_run_authorization_missing"],
                    }
                )
            return audit

    optional: dict[str, Any] = {}
    if adapter_resolver is not None:
        optional["adapter_resolver"] = adapter_resolver
    if input_loader is not None:
        optional["input_loader"] = input_loader
    if executor is not None:
        optional["executor"] = executor
    return dict(
        run_generic(
            repo_root,
            preregistration_path=preregistration_path,
            candidate_id=candidate_id,
            output_root=output_root,
            data_root=data_root,
            git_executable=git_executable,
            preregistration_validator=preregistration_validator,
            freeze_auditor=effective_auditor,
            authorization_path=authorization_path,
            authorization_validator=(
                lambda authorization, preregistration: verify_v36_formal_run_authorization(
                    authorization, preregistration=preregistration
                )
            ),
            run_id=f"{candidate_id}-v36-formal-001",
            **optional,
        )
    )


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
