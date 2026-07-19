"""Independent-process runner for deterministic, offline research candidates."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ast_policy import inspect_candidate_source
from .resource_limits import ResourceLimits


_WORKER = r"""
import json, sys
payload = json.loads(sys.stdin.read())
scope = {"__builtins__": {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "float": float, "int": int, "len": len,
    "list": list, "max": max, "min": min, "range": range, "round": round,
    "set": set, "sorted": sorted, "str": str, "sum": sum, "tuple": tuple,
    "zip": zip,
}}
exec(compile(payload["source"], "<generated-candidate>", "exec"), scope, scope)
result = scope["generate"](payload["context"])
sys.stdout.write(json.dumps({"ok": True, "output": result}, sort_keys=True, allow_nan=False))
"""


@dataclass(frozen=True)
class SandboxResult:
    status: str
    output: Any
    error: str | None
    audit: dict[str, Any]


def _minimal_environment(run_directory: Path) -> tuple[dict[str, str], list[str]]:
    allowed = ("COMSPEC", "PATH", "PATHEXT", "SystemRoot", "WINDIR")
    environment = {name: os.environ[name] for name in allowed if name in os.environ}
    environment.update(
        {
            "HOME": str(run_directory),
            "TEMP": str(run_directory),
            "TMP": str(run_directory),
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
        }
    )
    inherited_secrets = [
        name
        for name in environment
        if any(token in name.upper() for token in ("KEY", "SECRET", "TOKEN", "PASSWORD"))
    ]
    return environment, inherited_secrets


def run_candidate(
    source: str,
    context: dict[str, Any],
    *,
    limits: ResourceLimits | None = None,
    run_directory: Path | None = None,
) -> SandboxResult:
    limits = limits or ResourceLimits()
    source_audit = inspect_candidate_source(source)
    base_audit: dict[str, Any] = {
        **source_audit.to_dict(),
        "offline": True,
        "deterministicHashSeed": 0,
        "maxProcesses": limits.maxProcesses,
        "memoryMb": limits.memoryMb,
        "timeoutSeconds": limits.timeoutSeconds,
        "processIsolation": "independent_python_process",
        "wallClockEnforcement": "hard_timeout",
        "memoryEnforcement": "declared_limit_not_os_enforced",
        "securityBoundary": "research_execution_guard_not_os_security_boundary",
    }
    if not source_audit.passed:
        return SandboxResult("rejected", None, ";".join(source_audit.reasons), base_audit)

    payload = json.dumps(
        {"source": source, "context": context}, sort_keys=True, allow_nan=False
    ).encode("utf-8")
    if len(payload) > limits.maxInputBytes:
        return SandboxResult("rejected", None, "input_limit_exceeded", base_audit)

    run_root = Path(run_directory or Path.cwd() / ".test-temp" / "candidate-sandbox")
    run_root.mkdir(parents=True, exist_ok=True)
    environment, inherited_secrets = _minimal_environment(run_root)
    base_audit["inheritedSecretEnvironmentKeys"] = inherited_secrets
    process = subprocess.Popen(
        [sys.executable, "-I", "-S", "-c", _WORKER],
        cwd=run_root,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        stdout, stderr = process.communicate(payload, timeout=limits.timeoutSeconds)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        return SandboxResult("timeout", None, "wall_clock_timeout", base_audit)
    if len(stdout) > limits.maxOutputBytes:
        return SandboxResult("rejected", None, "output_limit_exceeded", base_audit)
    if process.returncode != 0:
        error = stderr.decode("utf-8", errors="replace").strip()
        return SandboxResult("failed", None, error or "candidate_process_failed", base_audit)
    try:
        response = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return SandboxResult("failed", None, f"invalid_candidate_output:{exc}", base_audit)
    return SandboxResult("passed", response.get("output"), None, base_audit)
