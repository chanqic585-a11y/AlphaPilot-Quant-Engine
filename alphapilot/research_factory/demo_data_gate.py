"""Data-only gate between a formal result and Demo release eligibility."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


def evaluate_demo_data_gate(
    *,
    formal_ready: bool,
    demo_ready: bool,
    exchange_portability: Mapping[str, Any],
) -> dict[str, Any]:
    checks = {
        "formalReady": bool(formal_ready),
        "demoReady": bool(demo_ready),
        "crossExchangePortabilityVerified": str(
            exchange_portability.get("crossExchangePortabilityStatus")
        )
        == "verified",
    }
    failed = [name for name, passed in checks.items() if not passed]
    payload: dict[str, Any] = {
        "schemaVersion": "demo_data_gate_v1",
        "status": "ready_for_demo_release"
        if not failed
        else "demo_data_blocked_before_release",
        "releaseEligible": not failed,
        "checks": checks,
        "failedConditions": failed,
        "approvalCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    payload["gateHash"] = stable_hash(payload, prefix="demo_data_gate")
    return payload
