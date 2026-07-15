"""Phase 3B fail-closed exit gate."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def evaluate_data_readiness(
    mechanisms: Sequence[dict[str, Any]],
    *,
    manifest_verified: bool,
    controls_verified: bool,
    trial_ledger_complete: bool,
    fdr_complete: bool,
    clusters_complete: bool,
    shortlist_frozen: bool,
    pit_status: str,
) -> dict[str, Any]:
    ready = [item for item in mechanisms if item.get("ready")]
    blockers: list[str] = []
    checks = {
        "manifest_verified": manifest_verified,
        "controls_verified": controls_verified,
        "trial_ledger_complete": trial_ledger_complete,
        "fdr_complete": fdr_complete,
        "clusters_complete": clusters_complete,
        "shortlist_frozen": shortlist_frozen,
        "pit_status_explicit": pit_status in {"verified_point_in_time", "diagnostic_proxy", "unavailable"},
        "minimum_mechanism_families": len(ready) >= 3,
        "non_ohlcv_mechanism_ready": any(item.get("usesNonOhlcv") for item in ready),
    }
    blockers.extend(name for name, passed in checks.items() if not passed)
    return {
        "schemaVersion": "phase3b_data_readiness_gate_v1",
        "passed": not blockers,
        "checks": checks,
        "blockers": blockers,
        "pitStatus": pit_status,
        "readyMechanismCount": len(ready),
        "readyMechanisms": [item["mechanismId"] for item in ready],
    }
