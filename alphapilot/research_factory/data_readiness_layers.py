"""Monotonic seven-layer data-readiness contract for V28-V32."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


READINESS_LAYER_ORDER = (
    "signal_ready",
    "ranking_ready",
    "capacity_ready",
    "prefilter_ready",
    "formal_ready",
    "release_ready",
    "demo_ready",
)


def build_layered_data_readiness(
    *,
    candidate_id: str,
    layer_specs: Mapping[str, Mapping[str, Any]],
    field_receipts: Mapping[str, Mapping[str, Any]],
    minimum_coverage_pct: float = 100.0,
) -> dict[str, Any]:
    """Evaluate each layer in order; a failed layer blocks every later layer."""

    if not candidate_id:
        raise ValueError("candidate_id_missing")
    if set(layer_specs) != set(READINESS_LAYER_ORDER):
        raise ValueError("readiness_layer_set_incomplete")
    if not 0.0 <= float(minimum_coverage_pct) <= 100.0:
        raise ValueError("invalid_minimum_coverage")

    rows: list[dict[str, Any]] = []
    previous_ready = True
    for layer in READINESS_LAYER_ORDER:
        spec = dict(layer_specs[layer])
        required = sorted(
            {str(value) for value in spec.get("requiredFields", []) if str(value)}
        )
        missing_policy = str(spec.get("missingPolicy") or "fail_closed")
        failed: list[str] = []
        available_at_rules: dict[str, str] = {}
        eligible_starts: list[str] = []
        coverage: dict[str, float] = {}
        for field in required:
            receipt = dict(field_receipts.get(field) or {})
            field_coverage = float(receipt.get("coveragePct") or 0.0)
            coverage[field] = field_coverage
            available_at_rule = str(receipt.get("availableAtRule") or "")
            available_at_rules[field] = available_at_rule
            eligible_start = str(receipt.get("firstEligibleSignalTimestamp") or "")
            if eligible_start:
                eligible_starts.append(eligible_start)
            if receipt.get("semanticsVerified") is not True:
                failed.append(f"unverified_semantics:{field}")
            if field_coverage < float(minimum_coverage_pct):
                failed.append(f"insufficient_coverage:{field}")
            if not available_at_rule:
                failed.append(f"missing_available_at:{field}")
            if not eligible_start:
                failed.append(f"missing_eligible_start:{field}")
        own_ready = bool(required) and not failed and missing_policy == "fail_closed"
        ready = previous_ready and own_ready
        if not previous_ready:
            failed.insert(0, "prior_layer_not_ready")
        row: dict[str, Any] = {
            "layer": layer,
            "requiredFields": required,
            "semantics": "verified_causal_fields_only",
            "minimumCoveragePct": float(minimum_coverage_pct),
            "coverageByField": coverage,
            "availableAtRules": available_at_rules,
            "eligibleStartTimestamp": max(eligible_starts) if eligible_starts else None,
            "missingPolicy": missing_policy,
            "ready": ready,
            "failedConditions": failed,
        }
        row["layerHash"] = stable_hash(row, prefix=f"data_readiness_{layer}")
        rows.append(row)
        previous_ready = ready

    readiness = {row["layer"]: bool(row["ready"]) for row in rows}
    payload: dict[str, Any] = {
        "schemaVersion": "layered_data_readiness_v1",
        "candidateId": candidate_id,
        "layers": rows,
        "signalReady": readiness["signal_ready"],
        "rankingReady": readiness["ranking_ready"],
        "capacityReady": readiness["capacity_ready"],
        "prefilterReady": readiness["prefilter_ready"],
        "formalReady": readiness["formal_ready"],
        "releaseReady": readiness["release_ready"],
        "demoReady": readiness["demo_ready"],
    }
    payload["contractHash"] = stable_hash(payload, prefix="layered_data_readiness")
    return payload

