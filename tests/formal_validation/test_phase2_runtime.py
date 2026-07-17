from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from alphapilot.formal_validation.freqtrade_runtime import (
    PINNED_FREQTRADE_IMAGE,
    build_runtime_manifest,
    build_runtime_smoke,
    parse_freqtrade_version_output,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


VERSION_OUTPUT = """\
Operating System:\tLinux
Python Version:\t\tPython 3.14.6
CCXT Version:\t\t4.5.61

Freqtrade Version:\tfreqtrade 2026.6
"""


def test_runtime_manifest_is_digest_pinned_and_reproducible() -> None:
    observed = parse_freqtrade_version_output(VERSION_OUTPUT)
    lock_text = "freqtrade==2026.6\nccxt==4.5.61\n"

    payload = build_runtime_manifest(
        image_reference=PINNED_FREQTRADE_IMAGE,
        observed_versions=observed,
        dependency_lock_text=lock_text,
        docker_server_version="29.6.1",
    )

    assert "@sha256:" in payload["imageReference"]
    assert payload["imageDigest"] == (
        "sha256:87aa5c6d65359b34e9d99a0bb260a38c0efe0315253811e6f48c2afe8f278a6a"
    )
    assert payload["freqtradeVersion"] == "2026.6"
    assert payload["pythonVersion"] == "3.14.6"
    assert payload["ccxtVersion"] == "4.5.61"
    assert payload["timezone"] == "UTC"
    assert payload["randomSeeds"] == [13, 27, 111]
    assert len(payload["dependencyLockSha256"]) == 64
    assert payload["status"] == "pinned"


def test_runtime_manifest_rejects_mutable_tag() -> None:
    with pytest.raises(ValueError, match="digest-pinned"):
        build_runtime_manifest(
            image_reference="freqtradeorg/freqtrade:stable",
            observed_versions=parse_freqtrade_version_output(VERSION_OUTPUT),
            dependency_lock_text="freqtrade==2026.6\n",
            docker_server_version="29.6.1",
        )


def test_runtime_smoke_fails_closed_and_records_zero_side_effects() -> None:
    smoke = build_runtime_smoke(
        image_reference=PINNED_FREQTRADE_IMAGE,
        command_results={
            "cliStartup": {"returnCode": 0, "detail": "freqtrade 2026.6"},
            "configParse": {"returnCode": 0, "detail": "config parsed"},
            "strategyLoad": {"returnCode": 0, "detail": "AlphaPilotS01BearRecovery4H"},
            "exitHooks": {"returnCode": 0, "detail": "callable"},
        },
        network_mode="none",
    )

    assert smoke["status"] == "passed"
    assert smoke["networkMode"] == "none"
    assert smoke["networkAccessCount"] == 0
    assert smoke["credentialReadCount"] == 0
    assert smoke["accountAccessCount"] == 0
    assert smoke["lockedOosContentReadCount"] == 0
    assert smoke["formalResultCount"] == 0
    assert smoke["releaseCount"] == 0
    assert smoke["demoArm"] is False
    assert smoke["orderCount"] == 0

    failed = build_runtime_smoke(
        image_reference=PINNED_FREQTRADE_IMAGE,
        command_results={
            "cliStartup": {"returnCode": 1, "detail": "failed"},
            "configParse": {"returnCode": 0, "detail": "config parsed"},
            "strategyLoad": {"returnCode": 0, "detail": "loaded"},
            "exitHooks": {"returnCode": 0, "detail": "callable"},
        },
        network_mode="none",
    )
    assert failed["status"] == "blocked"


def test_runtime_audit_entrypoint_exists_and_loads() -> None:
    script = REPO_ROOT / "scripts" / "audit_freqtrade_runtime.py"
    assert script.is_file()

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ModuleNotFoundError" not in result.stderr
