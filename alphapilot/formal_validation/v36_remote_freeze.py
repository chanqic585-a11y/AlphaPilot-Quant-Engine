"""Remote publication audit for the V36 TSMOM Formal handoff."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping


def evaluate_v36_remote_freeze(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    checks = (
        ("upstreamContainsHead", "head_not_published"),
        ("headContainsImplementationCommit", "implementation_commit_not_in_frozen_head"),
        ("upstreamContainsImplementationCommit", "implementation_commit_not_published"),
        ("worktreeClean", "worktree_not_clean"),
        ("preregistrationTracked", "preregistration_not_tracked"),
        ("preregistrationClean", "preregistration_has_local_changes"),
        ("preregistrationOnUpstream", "preregistration_not_published"),
        ("preregistrationBytesMatch", "preregistration_remote_bytes_mismatch"),
        ("snapshotTracked", "snapshot_not_tracked"),
        ("snapshotClean", "snapshot_has_local_changes"),
        ("snapshotOnUpstream", "snapshot_not_published"),
        ("snapshotBytesMatch", "snapshot_remote_bytes_mismatch"),
    )
    for field, blocker in checks:
        if not snapshot.get(field):
            blockers.append(blocker)
    if not str(snapshot.get("implementationCommit") or ""):
        blockers.append("implementation_commit_not_frozen")
    tag = str(snapshot.get("remoteFreezeTag") or "")
    tag_commit = str(snapshot.get("remoteTagCommit") or "")
    if not tag or not tag_commit:
        blockers.append("remote_freeze_tag_missing")
    elif tag_commit != str(snapshot.get("headCommit") or ""):
        blockers.append("remote_freeze_tag_not_at_head")
    blockers = sorted(set(blockers))
    return {
        "schemaVersion": "v36_tsmom_remote_freeze_audit_v1",
        "status": "blocked" if blockers else "passed",
        "route": "blocked_remote_freeze" if blockers else "ready_for_authorization",
        "blockers": blockers,
        "headCommit": snapshot.get("headCommit"),
        "implementationCommit": snapshot.get("implementationCommit"),
        "upstreamRef": snapshot.get("upstreamRef"),
        "remoteFreezeTag": tag or None,
        "remoteTagCommit": tag_commit or None,
        "formalRunCount": 0,
        "formalInputReadCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


def _run_git(
    root: Path, executable: str, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [executable, *args],
        cwd=root,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _run_git_bytes(
    root: Path, executable: str, *args: str
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [executable, *args],
        cwd=root,
        check=False,
        capture_output=True,
    )


def _remote_tag_commit(root: Path, executable: str, remote: str, tag: str) -> str | None:
    result = _run_git(
        root,
        executable,
        "ls-remote",
        "--tags",
        remote,
        f"refs/tags/{tag}",
        f"refs/tags/{tag}^{{}}",
        check=False,
    )
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


def _remote_file_state(
    *, root: Path, executable: str, upstream: str, path: Path
) -> dict[str, Any]:
    relative = path.resolve().relative_to(root).as_posix()
    remote = _run_git_bytes(root, executable, "show", f"{upstream}:{relative}")
    local_bytes = path.read_bytes() if path.is_file() else b""
    remote_bytes = remote.stdout if remote.returncode == 0 else b""
    return {
        "tracked": _run_git(
            root,
            executable,
            "ls-files",
            "--error-unmatch",
            "--",
            relative,
            check=False,
        ).returncode
        == 0,
        "clean": not _run_git(
            root, executable, "status", "--porcelain", "--", relative
        ).stdout.strip(),
        "onUpstream": remote.returncode == 0,
        "bytesMatch": bool(
            local_bytes
            and remote_bytes
            and hashlib.sha256(local_bytes).digest()
            == hashlib.sha256(remote_bytes).digest()
        ),
    }


def audit_v36_remote_freeze(
    *,
    repo_root: Path,
    preregistration_path: Path,
    git_executable: str | None = None,
    remote: str = "origin",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    prereg_path = Path(preregistration_path).resolve()
    executable = git_executable or shutil.which("git")
    if not executable or not prereg_path.is_file():
        return evaluate_v36_remote_freeze({})
    preregistration = json.loads(prereg_path.read_text(encoding="utf-8"))
    snapshot_id = str(preregistration.get("dataSnapshotId") or "")
    snapshot_path = root / "research" / "data_snapshots" / f"{snapshot_id}.json"
    implementation = str(preregistration.get("implementationCommit") or "")
    freeze_tag = str(
        dict(preregistration.get("remoteFreezePolicy") or {}).get("tag") or ""
    )
    head = _run_git(root, executable, "rev-parse", "HEAD").stdout.strip()
    upstream_result = _run_git(
        root, executable, "rev-parse", "--abbrev-ref", "@{upstream}", check=False
    )
    upstream = upstream_result.stdout.strip() if upstream_result.returncode == 0 else ""
    prereg_state = _remote_file_state(
        root=root, executable=executable, upstream=upstream, path=prereg_path
    )
    snapshot_state = _remote_file_state(
        root=root, executable=executable, upstream=upstream, path=snapshot_path
    )

    def _ancestor(older: str, newer: str) -> bool:
        return bool(
            older
            and newer
            and _run_git(
                root,
                executable,
                "merge-base",
                "--is-ancestor",
                older,
                newer,
                check=False,
            ).returncode
            == 0
        )

    return evaluate_v36_remote_freeze(
        {
            "headCommit": head,
            "implementationCommit": implementation,
            "upstreamRef": upstream or None,
            "upstreamContainsHead": _ancestor(head, upstream),
            "headContainsImplementationCommit": _ancestor(implementation, head),
            "upstreamContainsImplementationCommit": _ancestor(implementation, upstream),
            "worktreeClean": not _run_git(root, executable, "status", "--porcelain").stdout.strip(),
            "preregistrationTracked": prereg_state["tracked"],
            "preregistrationClean": prereg_state["clean"],
            "preregistrationOnUpstream": prereg_state["onUpstream"],
            "preregistrationBytesMatch": prereg_state["bytesMatch"],
            "snapshotTracked": snapshot_state["tracked"],
            "snapshotClean": snapshot_state["clean"],
            "snapshotOnUpstream": snapshot_state["onUpstream"],
            "snapshotBytesMatch": snapshot_state["bytesMatch"],
            "remoteFreezeTag": freeze_tag,
            "remoteTagCommit": _remote_tag_commit(root, executable, remote, freeze_tag),
        }
    )
