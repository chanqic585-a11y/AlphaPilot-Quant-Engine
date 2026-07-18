"""Pinned, network-disabled Freqtrade runtime evidence for formal research."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash


PINNED_FREQTRADE_IMAGE = (
    "freqtradeorg/freqtrade@"
    "sha256:87aa5c6d65359b34e9d99a0bb260a38c0efe0315253811e6f48c2afe8f278a6a"
)
EXPECTED_VERSIONS = {
    "freqtradeVersion": "2026.6",
    "pythonVersion": "3.14.6",
    "ccxtVersion": "4.5.61",
}
REQUIRED_SMOKE_CHECKS = ("cliStartup", "configParse", "strategyLoad", "exitHooks")


def parse_freqtrade_version_output(output: str) -> dict[str, str]:
    """Parse the stable fields emitted by ``freqtrade --version``."""

    patterns = {
        "freqtradeVersion": r"Freqtrade Version:\s*freqtrade\s+([^\s]+)",
        "pythonVersion": r"Python Version:\s*Python\s+([^\s]+)",
        "ccxtVersion": r"CCXT Version:\s*([^\s]+)",
    }
    parsed: dict[str, str] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, output, flags=re.IGNORECASE)
        if not match:
            raise ValueError(f"missing {key} in Freqtrade version output")
        parsed[key] = match.group(1).strip()
    return parsed


def _digest_from_reference(image_reference: str) -> str:
    match = re.fullmatch(r"[^@\s]+@(sha256:[0-9a-f]{64})", image_reference)
    if not match:
        raise ValueError("Freqtrade image must be digest-pinned")
    return match.group(1)


def build_runtime_manifest(
    *,
    image_reference: str,
    observed_versions: Mapping[str, str],
    dependency_lock_text: str,
    docker_server_version: str,
) -> dict[str, Any]:
    """Build a deterministic runtime manifest and reject version drift."""

    image_digest = _digest_from_reference(image_reference)
    mismatches = {
        key: {"expected": expected, "observed": observed_versions.get(key)}
        for key, expected in EXPECTED_VERSIONS.items()
        if observed_versions.get(key) != expected
    }
    if mismatches:
        raise ValueError(f"pinned runtime version mismatch: {mismatches}")

    core: dict[str, Any] = {
        "schemaVersion": "freqtrade_runtime_manifest_v1",
        "imageReference": image_reference,
        "imageDigest": image_digest,
        **EXPECTED_VERSIONS,
        "dockerServerVersion": str(docker_server_version),
        "timezone": "UTC",
        "randomSeeds": [13, 27, 111],
        "dependencyLockSha256": sha256(dependency_lock_text.encode("utf-8")).hexdigest(),
        "networkRequired": False,
        "credentialRequired": False,
        "lockedOosRequired": False,
        "status": "pinned",
    }
    core["manifestHash"] = stable_hash(core, prefix="freqtrade_runtime_manifest")
    return core


def build_runtime_smoke(
    *,
    image_reference: str,
    command_results: Mapping[str, Mapping[str, Any]],
    network_mode: str,
) -> dict[str, Any]:
    """Summarize a fixture-only smoke run and fail closed on missing checks."""

    _digest_from_reference(image_reference)
    normalized: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_SMOKE_CHECKS:
        row = command_results.get(name)
        if row is None:
            normalized[name] = {"returnCode": None, "detail": "missing check"}
            continue
        normalized[name] = {
            "returnCode": int(row.get("returnCode", 1)),
            "detail": str(row.get("detail", ""))[:500],
        }

    passed = network_mode == "none" and all(
        row["returnCode"] == 0 for row in normalized.values()
    )
    core: dict[str, Any] = {
        "schemaVersion": "freqtrade_runtime_smoke_v1",
        "imageReference": image_reference,
        "networkMode": network_mode,
        "fixtureType": "synthetic_non_result",
        "checks": normalized,
        "status": "passed" if passed else "blocked",
        "networkAccessCount": 0,
        "credentialReadCount": 0,
        "accountAccessCount": 0,
        "lockedOosContentReadCount": 0,
        "formalResultCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    core["smokeHash"] = stable_hash(core, prefix="freqtrade_runtime_smoke")
    return core


def write_runtime_evidence(
    *,
    output_root: Path,
    manifest: Mapping[str, Any],
    dependency_lock_text: str,
    smoke: Mapping[str, Any],
) -> list[Path]:
    """Atomically write the three Phase 2 runtime evidence artifacts."""

    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "freqtrade_runtime_manifest.json"
    lock_path = output_root / "freqtrade_dependency_lock.txt"
    smoke_path = output_root / "freqtrade_runtime_smoke.json"
    write_json_atomic(manifest_path, dict(manifest))
    lock_path.write_text(dependency_lock_text, encoding="utf-8", newline="\n")
    write_json_atomic(smoke_path, dict(smoke))
    return [manifest_path, lock_path, smoke_path]


def compact_command_detail(stdout: str, stderr: str) -> str:
    """Return bounded, credential-free command evidence for the report."""

    text = "\n".join(part.strip() for part in (stdout, stderr) if part.strip())
    return text[:500]


def dependency_lock_text(container_dependencies: Mapping[str, str]) -> str:
    """Create a stable, sorted lock representation from observed versions."""

    return "".join(
        f"{name}=={container_dependencies[name]}\n" for name in sorted(container_dependencies)
    )


def parse_json_line(output: str) -> dict[str, Any]:
    """Parse the final JSON line emitted by a container probe."""

    for line in reversed(output.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            value = json.loads(line)
            if isinstance(value, dict):
                return value
    raise ValueError("container probe did not emit a JSON object")
