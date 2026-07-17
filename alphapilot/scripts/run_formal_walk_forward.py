"""Run a remote-frozen V18 formal candidate exactly once."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.formal_validation.candidate_adapter import CandidateAdapter
from alphapilot.formal_validation.candidate_adapters import get_candidate_adapter
from alphapilot.formal_validation.formal_input import load_formal_input
from alphapilot.formal_validation.formal_run_ledger import (
    claim_formal_run,
    complete_formal_run,
    fail_formal_run,
)
from alphapilot.formal_validation.v18_contracts import verify_v18_preregistration
from alphapilot.formal_validation.v18_formal_reporting import (
    execute_v18_formal_campaign,
)
from alphapilot.formal_validation.v18_remote_freeze import audit_v18_remote_freeze


AdapterResolver = Callable[[str], CandidateAdapter]


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("V18 preregistration must be a JSON object")
    return payload


def _safe_identity(value: str, *, label: str) -> str:
    normalized = str(value or "").strip()
    if (
        not normalized
        or normalized in {".", ".."}
        or Path(normalized).name != normalized
        or "/" in normalized
        or "\\" in normalized
    ):
        raise ValueError(f"invalid_{label}:{normalized}")
    return normalized


def formal_artifact_root(
    output_root: Path,
    *,
    campaign_id: str,
    candidate_id: str,
) -> Path:
    """Return the deterministic campaign/candidate-scoped artifact leaf."""

    campaign = _safe_identity(campaign_id, label="campaign_id")
    candidate = _safe_identity(candidate_id, label="candidate_id")
    return Path(output_root).resolve() / campaign / candidate


def _blocked_route(audit: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "v18_formal_run_route_v2",
        "route": "blocked_remote_freeze",
        "blockers": list(audit.get("blockers", [])),
        "formalRunCount": 0,
        "formalInputReadCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


def _default_executor(**kwargs: Any) -> dict[str, Any]:
    return execute_v18_formal_campaign(**kwargs)


def run(
    repo_root: Path,
    *,
    preregistration_path: Path,
    candidate_id: str,
    output_root: Path,
    data_root: Path | None = None,
    git_executable: str | None = None,
    freeze_auditor: Callable[..., Mapping[str, Any]] = audit_v18_remote_freeze,
    adapter_resolver: AdapterResolver = get_candidate_adapter,
    input_loader: Callable[..., Any] = load_formal_input,
    executor: Callable[..., Mapping[str, Any]] = _default_executor,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Gate on remote freeze before resolving an adapter or opening input."""

    root = Path(repo_root).resolve()
    prereg_path = Path(preregistration_path).resolve()
    preregistration = _read_json(prereg_path)
    if not verify_v18_preregistration(preregistration):
        raise ValueError("V18 preregistration hash mismatch")
    requested_candidate_id = _safe_identity(candidate_id, label="candidate_id")
    frozen_candidate_id = str(preregistration.get("sourceCandidateId") or "")
    if requested_candidate_id != frozen_candidate_id:
        raise ValueError(
            "candidate_id_mismatch:"
            f"preregistration={frozen_candidate_id}:requested={requested_candidate_id}"
        )
    campaign_id = _safe_identity(
        str(preregistration.get("campaignId") or ""), label="campaign_id"
    )
    destination = formal_artifact_root(
        output_root,
        campaign_id=campaign_id,
        candidate_id=requested_candidate_id,
    )
    destination.mkdir(parents=True, exist_ok=True)

    audit = dict(
        freeze_auditor(
            repo_root=root,
            preregistration_path=prereg_path,
            git_executable=git_executable,
        )
    )
    write_json_atomic(destination / "remote_freeze_audit.json", audit)
    if audit.get("status") != "passed":
        route = _blocked_route(audit)
        write_json_atomic(destination / "formal_run_route.json", route)
        return route

    candidate_adapter = adapter_resolver(requested_candidate_id)
    identity = {
        "codeCommit": audit.get("headCommit"),
        "preregistrationHash": preregistration["preregistrationHash"],
        "inputSnapshotHash": preregistration["dataSnapshotHash"],
        "candidateId": requested_candidate_id,
        "candidateAdapterId": candidate_adapter.adapter_id,
        "candidateAdapterVersion": candidate_adapter.adapter_version,
    }
    effective_run_id = run_id or f"{requested_candidate_id}-v18-formal-001"
    ledger_path = destination / "formal_run_ledger.json"
    checkpoint = {
        "checkpointId": "before_formal_input_read",
        "deterministic": True,
    }
    claim_formal_run(
        ledger_path,
        run_id=effective_run_id,
        identity=identity,
        checkpoint=checkpoint,
        resume_checkpoint=checkpoint,
    )
    try:
        bundle = input_loader(
            repo_root=root,
            data_root=Path(data_root).resolve() if data_root else root,
            preregistration_path=prereg_path,
            candidate_id=requested_candidate_id,
            candidate_adapter=candidate_adapter,
            preregistration_validator=verify_v18_preregistration,
        )
        result = dict(
            executor(
                bundle=bundle,
                repo_root=root,
                output_root=destination,
                candidate_adapter=candidate_adapter,
            )
        )
        manifest_hash = str(result.get("resultManifestHash") or "")
        if not manifest_hash:
            raise RuntimeError("V18 executor did not return resultManifestHash")
    except Exception as error:
        fail_formal_run(
            ledger_path,
            run_id=effective_run_id,
            identity=identity,
            reason=type(error).__name__,
        )
        raise
    complete_formal_run(
        ledger_path,
        run_id=effective_run_id,
        identity=identity,
        result_manifest_hash=manifest_hash,
    )
    route = {
        "schemaVersion": "v18_formal_run_route_v2",
        "route": str(result.get("route") or "formal_run_completed"),
        "campaignId": campaign_id,
        "candidateId": requested_candidate_id,
        "formalRunCount": 1,
        "formalInputReadCount": 1,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "resultManifestHash": manifest_hash,
    }
    write_json_atomic(destination / "formal_run_route.json", route)
    return route


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--git-executable")
    args = parser.parse_args(argv)
    route = run(
        args.repo_root,
        preregistration_path=args.preregistration,
        candidate_id=args.candidate_id,
        output_root=args.output_root,
        data_root=args.data_root,
        git_executable=args.git_executable,
    )
    print(json.dumps(route, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
