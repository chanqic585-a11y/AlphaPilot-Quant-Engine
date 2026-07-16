"""Locked Qlib preflight without importing, training, or running Qlib."""

from __future__ import annotations

from typing import Any


QLIB_COMMIT = "d5379c520f66a39953bad76234a7019a72796fd0"


def build_qlib_preflight(
    *,
    c_status: str,
    pit_metrics: dict[str, Any],
    snapshot: dict[str, Any],
    environment: dict[str, Any],
) -> dict[str, Any]:
    checks = {
        "c_formal_ready": c_status == "formal_ready",
        "pit_median_at_least_30": int(pit_metrics.get("medianInvestableContracts") or 0) >= 30,
        "fresh_holdout_ready": bool(pit_metrics.get("freshHoldoutReady")),
        "snapshot_hash_verified": bool(snapshot.get("hashVerified"))
        and bool(snapshot.get("snapshotHash")),
        "data_only_snapshot": not snapshot.get("containsStrategyResults")
        and not snapshot.get("containsHoldoutResults"),
        "docker_daemon_available": bool(environment.get("dockerDaemonAvailable")),
        "docker_image_available": bool(environment.get("dockerImageAvailable")),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    may_run = not blockers
    return {
        "schemaVersion": "v13_27_1_12_qlib_preflight_v1",
        "qlibCommit": QLIB_COMMIT,
        "license": "MIT",
        "licenseUrl": "https://github.com/microsoft/qlib/blob/main/LICENSE",
        "sourceUrl": f"https://github.com/microsoft/qlib/tree/{QLIB_COMMIT}",
        "installationAttempted": False,
        "modelCampaignRun": False,
        "syntheticAdapterTestAllowed": True,
        "informalSnapshotParityTestAllowed": True,
        "dockerReproducibilityPassed": checks["docker_daemon_available"]
        and checks["docker_image_available"],
        "checks": checks,
        "blockers": blockers,
        "qlibCampaignMayRun": may_run,
    }
