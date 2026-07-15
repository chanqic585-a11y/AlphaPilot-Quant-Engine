"""Capture the execution environment that can change research results."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import locale
import platform
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _version(package: str) -> str | None:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def _default_command_output(command: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def _safe_command(
    runner: Callable[[str, Path | None], str],
    command: str,
    cwd: Path | None = None,
) -> str | None:
    try:
        return runner(command, cwd).strip()
    except (OSError, subprocess.SubprocessError, KeyError):
        return None


def build_environment_manifest(
    *,
    repo_paths: Mapping[str, Path],
    dependency_lock_path: Path,
    command_output: Callable[[str, Path | None], str] = _default_command_output,
    python_executable: str = sys.executable,
    docker_image_tag: str = "freqtradeorg/freqtrade:stable",
    random_seeds: Sequence[int] = (13, 27, 111),
) -> dict[str, Any]:
    lock_bytes = dependency_lock_path.read_bytes()
    python_command = f'"{python_executable}"' if " " in python_executable else python_executable
    pip_freeze = (
        _safe_command(command_output, f"{python_command} -m pip freeze --all") or ""
    )
    commits = {
        name: _safe_command(command_output, "git rev-parse HEAD", path)
        for name, path in sorted(repo_paths.items())
    }
    dependencies = {
        "pandas": _version("pandas"),
        "numpy": _version("numpy"),
        "pyarrow": _version("pyarrow"),
    }
    core = {
        "schemaVersion": "reproducibility_environment_manifest_v2",
        "operatingSystem": platform.platform(),
        "pythonExecutable": python_executable,
        "pythonVersion": platform.python_version(),
        "freqtradeVersion": _safe_command(
            command_output,
            f"{python_command} -m freqtrade --version",
        ),
        "dockerVersion": _safe_command(command_output, "docker --version"),
        "dockerImageTag": docker_image_tag,
        "dockerImageDigest": _safe_command(
            command_output,
            f"docker image inspect {docker_image_tag} --format {{{{.Id}}}}",
        ),
        "dependencyLockPath": str(dependency_lock_path),
        "dependencyLockHash": _sha256_bytes(lock_bytes),
        "pipFreezeHash": _sha256_bytes(pip_freeze.encode("utf-8")),
        "gitCommits": commits,
        "randomSeeds": list(random_seeds),
        "storageTimezone": "UTC",
        "displayTimezone": "Asia/Shanghai",
        "locale": locale.getlocale(),
        "dependencies": dependencies,
        "parquetPolicy": {
            "allowed": dependencies["pyarrow"] is not None
            and f"pyarrow=={dependencies['pyarrow']}" in lock_bytes.decode("utf-8"),
            "csvAndCanonicalJsonRequired": True,
        },
    }
    return {**core, "environmentHash": stable_hash(core, prefix="environment_manifest")}


def write_environment_manifest(path: Path, manifest: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
