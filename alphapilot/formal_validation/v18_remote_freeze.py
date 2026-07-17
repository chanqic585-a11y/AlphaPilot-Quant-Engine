"""Remote-publication gate for the one-shot V18 formal campaign."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping


V17_TAG = "v13.27.1.17"
V18_TAG = "v13.27.1.18"


def evaluate_v18_remote_freeze(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate publication evidence without opening formal market data."""

    blockers: list[str] = []
    if not snapshot.get("upstreamContainsHead"):
        blockers.append("head_not_published")
    if not snapshot.get("preregistrationTracked"):
        blockers.append("preregistration_not_tracked")
    if not snapshot.get("preregistrationClean"):
        blockers.append("preregistration_has_local_changes")
    if not snapshot.get("preregistrationOnUpstream"):
        blockers.append("preregistration_not_published")
    implementation_commit = str(snapshot.get("implementationCommit") or "")
    if not implementation_commit:
        blockers.append("implementation_commit_not_frozen")
    else:
        if not snapshot.get("headContainsImplementationCommit"):
            blockers.append("implementation_commit_not_in_frozen_head")
        if not snapshot.get("upstreamContainsImplementationCommit"):
            blockers.append("implementation_commit_not_published")

    tags = snapshot.get("remoteTags")
    remote_tags = dict(tags) if isinstance(tags, Mapping) else {}
    if not remote_tags.get(V17_TAG):
        blockers.append("remote_v17_tag_missing")
    v18_commit = str(remote_tags.get(V18_TAG) or "")
    if not v18_commit:
        blockers.append("remote_v18_tag_missing")
    elif v18_commit != str(snapshot.get("headCommit") or ""):
        blockers.append("remote_v18_tag_not_at_head")

    status = "blocked" if blockers else "passed"
    return {
        "schemaVersion": "s01_v18_remote_freeze_audit_v1",
        "status": status,
        "route": (
            "blocked_remote_freeze"
            if blockers
            else "ready_for_single_formal_run"
        ),
        "blockers": blockers,
        "headCommit": snapshot.get("headCommit"),
        "implementationCommit": implementation_commit or None,
        "upstreamRef": snapshot.get("upstreamRef"),
        "remoteTags": remote_tags,
        "formalInputReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


def _run_git(
    repo_root: Path,
    git_executable: str,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [git_executable, *args],
        cwd=repo_root,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _remote_tag_commit(
    repo_root: Path,
    git_executable: str,
    remote: str,
    tag: str,
) -> str | None:
    result = _run_git(
        repo_root,
        git_executable,
        "ls-remote",
        "--tags",
        remote,
        f"refs/tags/{tag}",
        f"refs/tags/{tag}^{{}}",
        check=False,
    )
    if result.returncode != 0:
        return None
    direct: str | None = None
    peeled: str | None = None
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        commit, ref = parts
        if ref.endswith("^{}"):
            peeled = commit
        elif ref.endswith(f"/{tag}"):
            direct = commit
    return peeled or direct


def audit_v18_remote_freeze(
    *,
    repo_root: Path,
    preregistration_path: Path,
    git_executable: str | None = None,
    remote: str = "origin",
) -> dict[str, Any]:
    """Collect Git publication evidence and evaluate the V18 freeze gate."""

    root = Path(repo_root).resolve()
    prereg = Path(preregistration_path).resolve()
    try:
        relative = prereg.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("preregistration_path must be inside repo_root") from exc
    executable = git_executable or shutil.which("git")
    if not executable:
        return evaluate_v18_remote_freeze(
            {
                "headCommit": None,
                "upstreamContainsHead": False,
                "preregistrationTracked": False,
                "preregistrationClean": False,
                "preregistrationOnUpstream": False,
                "remoteTags": {},
            }
        )

    head = _run_git(root, executable, "rev-parse", "HEAD").stdout.strip()
    preregistration = (
        json.loads(prereg.read_text(encoding="utf-8")) if prereg.is_file() else {}
    )
    implementation_commit = str(
        preregistration.get("implementationCommit") or ""
    ).strip()
    upstream_result = _run_git(
        root, executable, "rev-parse", "--abbrev-ref", "@{upstream}", check=False
    )
    upstream = upstream_result.stdout.strip() if upstream_result.returncode == 0 else ""
    contains = False
    head_contains_implementation = False
    upstream_contains_implementation = False
    prereg_on_upstream = False
    if implementation_commit:
        head_contains_implementation = (
            _run_git(
                root,
                executable,
                "merge-base",
                "--is-ancestor",
                implementation_commit,
                head,
                check=False,
            ).returncode
            == 0
        )
    if upstream:
        contains = (
            _run_git(
                root,
                executable,
                "merge-base",
                "--is-ancestor",
                head,
                upstream,
                check=False,
            ).returncode
            == 0
        )
        prereg_on_upstream = (
            _run_git(
                root,
                executable,
                "cat-file",
                "-e",
                f"{upstream}:{relative}",
                check=False,
            ).returncode
            == 0
        )
        if implementation_commit:
            upstream_contains_implementation = (
                _run_git(
                    root,
                    executable,
                    "merge-base",
                    "--is-ancestor",
                    implementation_commit,
                    upstream,
                    check=False,
                ).returncode
                == 0
            )
    tracked = (
        _run_git(
            root,
            executable,
            "ls-files",
            "--error-unmatch",
            "--",
            relative,
            check=False,
        ).returncode
        == 0
    )
    clean = not _run_git(
        root, executable, "status", "--porcelain", "--", relative
    ).stdout.strip()
    snapshot = {
        "headCommit": head,
        "implementationCommit": implementation_commit or None,
        "upstreamRef": upstream or None,
        "upstreamContainsHead": contains,
        "headContainsImplementationCommit": head_contains_implementation,
        "upstreamContainsImplementationCommit": upstream_contains_implementation,
        "preregistrationTracked": tracked,
        "preregistrationClean": clean,
        "preregistrationOnUpstream": prereg_on_upstream,
        "remoteTags": {
            V17_TAG: _remote_tag_commit(root, executable, remote, V17_TAG),
            V18_TAG: _remote_tag_commit(root, executable, remote, V18_TAG),
        },
    }
    return evaluate_v18_remote_freeze(snapshot)
