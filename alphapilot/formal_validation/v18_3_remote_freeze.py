"""Remote publication gates for V18.3 fold and ranking evidence closure."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from .v18_1_remote_freeze import _remote_tag_commit, _run_git, _run_git_bytes


V18_TAG = "v13.27.1.18"
V18_TAG_COMMIT = "aa2df4b5e8fc4e9c447edd3c5fef0a03de26ec01"
V18_1_TAG = "v13.27.1.18.1"
V18_1_TAG_COMMIT = "b60d0e191431a353e79f9c954c31d4de0be25c92"
V18_2_TAG = "v13.27.1.18.2-r2"
V18_2_TAG_COMMIT = "305a934a8c99e20185ea2bd2d7f1213e9985b224"


def evaluate_v18_3_code_freeze(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    local = str(snapshot.get("localCommit") or "")
    remote = str(snapshot.get("remoteCommit") or "")
    if not snapshot.get("upstreamContainsImplementationCommit"):
        blockers.append("implementation_commit_not_published")
    if not local or local != remote:
        blockers.append("implementation_commit_remote_mismatch")
    if not snapshot.get("worktreeClean"):
        blockers.append("worktree_not_clean")
    return {
        "schemaVersion": "s01_v18_3_remote_code_freeze_audit_v1",
        "status": "blocked" if blockers else "passed",
        "route": "blocked_remote_freeze" if blockers else "code_frozen_remotely",
        "blockers": blockers,
        "branch": snapshot.get("branch"),
        "localCommit": local or None,
        "remoteCommit": remote or None,
        "headCommit": local or None,
        "pushed": not blockers,
        "hashMatch": bool(local and local == remote),
        "worktreeClean": snapshot.get("worktreeClean") is True,
    }


def evaluate_v18_3_preregistration_freeze(
    snapshot: Mapping[str, Any]
) -> dict[str, Any]:
    blockers: list[str] = []
    if snapshot.get("headCommit") != snapshot.get("upstreamCommit"):
        blockers.append("head_not_published")
    if not snapshot.get("upstreamContainsImplementationCommit"):
        blockers.append("implementation_commit_not_published")
    if not snapshot.get("preregistrationTracked"):
        blockers.append("preregistration_not_tracked")
    if not snapshot.get("preregistrationClean"):
        blockers.append("preregistration_has_local_changes")
    if not snapshot.get("preregistrationOnUpstream"):
        blockers.append("preregistration_not_published")
    local_hash = str(snapshot.get("localPreregistrationSha256") or "")
    remote_hash = str(snapshot.get("remotePreregistrationSha256") or "")
    if not local_hash or local_hash != remote_hash:
        blockers.append("preregistration_remote_hash_mismatch")
    tags_value = snapshot.get("remoteTags")
    tags = dict(tags_value) if isinstance(tags_value, Mapping) else {}
    predecessor_v18 = tags.get(V18_TAG) == V18_TAG_COMMIT
    predecessor_v18_1 = tags.get(V18_1_TAG) == V18_1_TAG_COMMIT
    predecessor_v18_2 = tags.get(V18_2_TAG) == V18_2_TAG_COMMIT
    if not predecessor_v18:
        blockers.append("predecessor_v18_tag_changed")
    if not predecessor_v18_1:
        blockers.append("predecessor_v18_1_tag_changed")
    if not predecessor_v18_2 or snapshot.get("v18_2TagIsAncestorOfHead") is not True:
        blockers.append("predecessor_v18_2_tag_changed")
    return {
        "schemaVersion": "s01_v18_3_remote_preregistration_freeze_audit_v1",
        "status": "blocked" if blockers else "passed",
        "route": "blocked_remote_freeze" if blockers else "ready_for_authorization",
        "blockers": blockers,
        "headCommit": snapshot.get("headCommit"),
        "upstreamCommit": snapshot.get("upstreamCommit"),
        "implementationCommit": snapshot.get("implementationCommit"),
        "preregistrationHash": snapshot.get("preregistrationHash"),
        "localPreregistrationSha256": local_hash or None,
        "remotePreregistrationSha256": remote_hash or None,
        "hashMatch": bool(local_hash and local_hash == remote_hash),
        "predecessorV18TagUnchanged": predecessor_v18,
        "predecessorV18_1TagUnchanged": predecessor_v18_1,
        "predecessorV18_2TagUnchanged": predecessor_v18_2,
        "remoteTags": tags,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


def audit_v18_3_code_freeze(
    *,
    repo_root: Path,
    implementation_commit: str,
    git_executable: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    executable = git_executable or shutil.which("git")
    if not executable:
        return evaluate_v18_3_code_freeze({})
    branch = _run_git(root, executable, "branch", "--show-current").stdout.strip()
    local = _run_git(root, executable, "rev-parse", "HEAD").stdout.strip()
    upstream_result = _run_git(
        root, executable, "rev-parse", "@{upstream}", check=False
    )
    remote = upstream_result.stdout.strip() if upstream_result.returncode == 0 else ""
    contains = bool(
        remote
        and _run_git(
            root,
            executable,
            "merge-base",
            "--is-ancestor",
            implementation_commit,
            remote,
            check=False,
        ).returncode
        == 0
    )
    return evaluate_v18_3_code_freeze(
        {
            "branch": branch,
            "localCommit": local,
            "remoteCommit": remote,
            "upstreamContainsImplementationCommit": contains,
            "worktreeClean": not _run_git(
                root, executable, "status", "--porcelain"
            ).stdout.strip(),
        }
    )


def audit_v18_3_preregistration_freeze(
    *,
    repo_root: Path,
    preregistration_path: Path,
    git_executable: str | None = None,
    remote: str = "origin",
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    preregistration = Path(preregistration_path).resolve()
    relative = preregistration.relative_to(root).as_posix()
    executable = git_executable or shutil.which("git")
    if not executable:
        return evaluate_v18_3_preregistration_freeze({})
    head = _run_git(root, executable, "rev-parse", "HEAD").stdout.strip()
    upstream_result = _run_git(
        root, executable, "rev-parse", "@{upstream}", check=False
    )
    upstream = upstream_result.stdout.strip() if upstream_result.returncode == 0 else ""
    payload = json.loads(preregistration.read_text(encoding="utf-8"))
    implementation = str(payload.get("correctionImplementationCommit") or "")
    remote_file = _run_git_bytes(
        root, executable, "show", f"{upstream}:{relative}", check=False
    )
    remote_bytes = remote_file.stdout if remote_file.returncode == 0 else b""
    local_hash = hashlib.sha256(preregistration.read_bytes()).hexdigest()
    remote_hash = hashlib.sha256(remote_bytes).hexdigest() if remote_bytes else ""
    remote_tags = {
        V18_TAG: _remote_tag_commit(root, executable, remote, V18_TAG),
        V18_1_TAG: _remote_tag_commit(root, executable, remote, V18_1_TAG),
        V18_2_TAG: _remote_tag_commit(root, executable, remote, V18_2_TAG),
    }
    return evaluate_v18_3_preregistration_freeze(
        {
            "headCommit": head,
            "upstreamCommit": upstream,
            "implementationCommit": implementation,
            "preregistrationHash": payload.get("preregistrationHash"),
            "upstreamContainsImplementationCommit": bool(
                upstream
                and implementation
                and _run_git(
                    root,
                    executable,
                    "merge-base",
                    "--is-ancestor",
                    implementation,
                    upstream,
                    check=False,
                ).returncode
                == 0
            ),
            "preregistrationTracked": _run_git(
                root,
                executable,
                "ls-files",
                "--error-unmatch",
                "--",
                relative,
                check=False,
            ).returncode
            == 0,
            "preregistrationClean": not _run_git(
                root, executable, "status", "--porcelain", "--", relative
            ).stdout.strip(),
            "preregistrationOnUpstream": remote_file.returncode == 0,
            "localPreregistrationSha256": local_hash,
            "remotePreregistrationSha256": remote_hash,
            "remoteTags": remote_tags,
            "v18_2TagIsAncestorOfHead": bool(
                remote_tags[V18_2_TAG]
                and head
                and _run_git(
                    root,
                    executable,
                    "merge-base",
                    "--is-ancestor",
                    remote_tags[V18_2_TAG],
                    head,
                    check=False,
                ).returncode
                == 0
            ),
        }
    )
