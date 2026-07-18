"""Certification gate for formal runtime evidence."""

from __future__ import annotations

from typing import Any, Mapping

from .freqtrade_runtime_loader import EXACT_RUNTIME_VERSIONS


def guard_runtime(report: Mapping[str, Any]) -> dict[str, Any]:
    checks = {
        "runtimeRequested": report.get("runtimeRequested") is True,
        "runtimeLoaded": report.get("runtimeLoaded") is True,
        "strategyLoaded": report.get("strategyLoaded") is True,
        "configLoaded": report.get("configLoaded") is True,
        "dataRootValidated": report.get("dataRootValidated") is True,
        "timerangeValidated": report.get("timerangeValidated") is True,
        "timezoneUtc": report.get("timezone") == "UTC",
        "networkDisabled": report.get("networkAccessCount") == 0,
        "lockedOosUnread": report.get("lockedOosReadCount") == 0,
        "noFallback": report.get("fallbackUsed") is False,
        "runtimeHashPresent": bool(report.get("runtimeHash")),
        "versionsExact": all(
            str(report.get(field)) == expected
            for field, expected in EXACT_RUNTIME_VERSIONS.items()
        ),
    }
    return {
        "schemaVersion": "freqtrade_runtime_guard_v1",
        "status": "certified" if all(checks.values()) else "blocked",
        "checks": checks,
        "failedChecks": [name for name, passed in checks.items() if not passed],
    }
