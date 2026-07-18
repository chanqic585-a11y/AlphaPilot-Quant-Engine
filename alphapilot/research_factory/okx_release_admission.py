"""Fail-closed OKX evidence admission and immutable Demo Release contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hmac
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


_REQUIRED_OKX_FIELDS = (
    "ohlcv",
    "quote_turnover",
    "funding",
    "instrument_state",
    "exact_usdt_swap_identity",
)

_MINIMUM_THRESHOLDS = {
    "minimumSignalTimestampParityPct": "signalTimestampParityPct",
    "minimumEventOverlapPct": "eventOverlapPct",
    "minimumReturnCorrelation": "returnCorrelation",
    "minimumDirectionParityPct": "directionParityPct",
}

_MAXIMUM_THRESHOLDS = {
    "maximumCapacityDifferencePct": "capacityDifferencePct",
    "maximumFundingDifferenceR": "fundingDifferenceR",
    "maximumCostDifferenceR": "costDifferenceR",
}

_PASS_RESULT_CLASSES = {
    "formal_pass",
    "research_pass_no_clean_holdout",
    "research_pass_funding_unavailable",
}


def _require_text(value: Any, error: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(error)
    return normalized


def build_okx_same_exchange_profile(
    *,
    candidate_id: str,
    instrument_ids: Sequence[str],
    field_receipts: Mapping[str, Mapping[str, Any]],
    immutable_manifest_hash: str,
) -> dict[str, Any]:
    """Build a frozen same-exchange evidence profile without fetching data."""

    normalized_candidate_id = _require_text(candidate_id, "candidate_id_missing")
    normalized_manifest_hash = _require_text(
        immutable_manifest_hash, "immutable_manifest_hash_missing"
    )
    normalized_instruments = sorted(
        {_require_text(value, "instrument_id_missing") for value in instrument_ids}
    )
    blockers: list[str] = []
    if not normalized_instruments:
        blockers.append("instrument_universe_empty")
    blockers.extend(
        f"invalid_instrument:{instrument_id}"
        for instrument_id in normalized_instruments
        if not instrument_id.endswith("-USDT-SWAP")
    )

    normalized_receipts: dict[str, dict[str, Any]] = {}
    for field in _REQUIRED_OKX_FIELDS:
        receipt = field_receipts.get(field)
        if receipt is None:
            blockers.append(f"missing:{field}")
            continue
        normalized = {
            "verified": receipt.get("verified") is True,
            "availableAt": str(receipt.get("availableAt") or "").strip(),
            "hash": str(receipt.get("hash") or "").strip(),
        }
        normalized_receipts[field] = normalized
        if not normalized["verified"]:
            blockers.append(f"unverified:{field}")
        if not normalized["availableAt"]:
            blockers.append(f"available_at_missing:{field}")
        if not normalized["hash"]:
            blockers.append(f"hash_missing:{field}")

    payload: dict[str, Any] = {
        "schemaVersion": "okx_same_exchange_release_profile_v1",
        "candidateId": normalized_candidate_id,
        "exchange": "okx",
        "market": "usdt_swap",
        "instrumentIds": normalized_instruments,
        "requiredFields": list(_REQUIRED_OKX_FIELDS),
        "fieldReceipts": normalized_receipts,
        "immutableManifestHash": normalized_manifest_hash,
        "blockers": sorted(set(blockers)),
        "status": "ready" if not blockers else "blocked_okx_data",
    }
    payload["profileHash"] = stable_hash(payload, prefix="okx_same_exchange_profile")
    return payload


def evaluate_portability_audit(
    *,
    candidate_id: str,
    source_exchange: str,
    target_exchange: str,
    metrics: Mapping[str, Any],
    frozen_thresholds: Mapping[str, Any],
    thresholds_frozen_before_results: bool,
) -> dict[str, Any]:
    """Evaluate an explicitly frozen cross-exchange portability policy."""

    normalized_candidate_id = _require_text(candidate_id, "candidate_id_missing")
    normalized_source = _require_text(source_exchange, "source_exchange_missing")
    normalized_target = _require_text(target_exchange, "target_exchange_missing")
    required_thresholds = set(_MINIMUM_THRESHOLDS) | set(_MAXIMUM_THRESHOLDS)
    missing_thresholds = sorted(required_thresholds - set(frozen_thresholds))
    if missing_thresholds:
        raise ValueError(f"portability_thresholds_missing:{','.join(missing_thresholds)}")

    normalized_thresholds = {
        key: float(frozen_thresholds[key]) for key in sorted(required_thresholds)
    }
    normalized_metrics: dict[str, float] = {}
    failed: list[str] = []
    for threshold_name, metric_name in _MINIMUM_THRESHOLDS.items():
        if metric_name not in metrics:
            failed.append(f"missing:{metric_name}")
            continue
        metric_value = float(metrics[metric_name])
        normalized_metrics[metric_name] = metric_value
        if metric_value < normalized_thresholds[threshold_name]:
            failed.append(threshold_name)
    for threshold_name, metric_name in _MAXIMUM_THRESHOLDS.items():
        if metric_name not in metrics:
            failed.append(f"missing:{metric_name}")
            continue
        metric_value = float(metrics[metric_name])
        normalized_metrics[metric_name] = metric_value
        if metric_value > normalized_thresholds[threshold_name]:
            failed.append(threshold_name)
    if not thresholds_frozen_before_results:
        failed.append("thresholds_not_frozen_before_results")

    threshold_payload = {
        "schemaVersion": "okx_portability_thresholds_v1",
        "thresholds": normalized_thresholds,
        "frozenBeforeResults": thresholds_frozen_before_results is True,
    }
    payload: dict[str, Any] = {
        "schemaVersion": "okx_portability_audit_v1",
        "candidateId": normalized_candidate_id,
        "sourceExchange": normalized_source,
        "targetExchange": normalized_target,
        "metrics": normalized_metrics,
        "frozenThresholds": normalized_thresholds,
        "thresholdsFrozenBeforeResults": thresholds_frozen_before_results is True,
        "thresholdHash": stable_hash(
            threshold_payload, prefix="okx_portability_thresholds"
        ),
        "failedThresholds": sorted(set(failed)),
        "status": "passed" if not failed else "blocked_okx_portability",
    }
    payload["auditHash"] = stable_hash(payload, prefix="okx_portability_audit")
    return payload


def build_immutable_release(
    *,
    campaign_id: str,
    candidate: Mapping[str, Any],
    result_class: str,
    okx_profile: Mapping[str, Any] | None,
    portability_audit: Mapping[str, Any] | None,
    evidence_summary: Mapping[str, Any],
    risk_overlay: Mapping[str, Any],
) -> dict[str, Any]:
    """Freeze a Release at the approval boundary, never at execution state."""

    normalized_campaign_id = _require_text(campaign_id, "campaign_id_missing")
    candidate_id = _require_text(candidate.get("candidateId"), "candidate_id_missing")
    candidate_hash = _require_text(
        candidate.get("candidateHash"), "candidate_hash_missing"
    )
    if result_class not in _PASS_RESULT_CLASSES:
        raise ValueError("release_candidate_not_passed")

    okx_ready = okx_profile is not None and okx_profile.get("status") == "ready"
    portability_ready = (
        portability_audit is not None
        and portability_audit.get("status") == "passed"
    )
    if not (okx_ready or portability_ready):
        raise ValueError("release_okx_admission_not_passed")
    risk_overlay_hash = _require_text(
        risk_overlay.get("riskOverlayHash"), "risk_overlay_hash_missing"
    )

    release_identity = {
        "campaignId": normalized_campaign_id,
        "candidateId": candidate_id,
        "candidateHash": candidate_hash,
        "riskOverlayHash": risk_overlay_hash,
    }
    payload: dict[str, Any] = {
        "schemaVersion": "immutable_demo_release_v1",
        "releaseId": stable_hash(
            release_identity, prefix="immutable_demo_release_identity"
        ),
        "campaignId": normalized_campaign_id,
        "candidateId": candidate_id,
        "candidateHash": candidate_hash,
        "resultClass": result_class,
        "admissionRoute": "okx_same_exchange" if okx_ready else "portability_audit",
        "okxProfileHash": okx_profile.get("profileHash") if okx_ready else None,
        "portabilityAuditHash": (
            portability_audit.get("auditHash") if portability_ready else None
        ),
        "evidenceSummary": dict(evidence_summary),
        "evidenceSummaryHash": stable_hash(
            dict(evidence_summary), prefix="immutable_release_evidence_summary"
        ),
        "riskOverlayHash": risk_overlay_hash,
        "approved": False,
        "demoArm": False,
        "orderCount": 0,
        "liveEnabled": False,
        "withdrawEnabled": False,
    }
    payload["releaseHash"] = stable_hash(payload, prefix="immutable_demo_release")
    return payload


def build_release_approval_request(release: Mapping[str, Any]) -> dict[str, Any]:
    """Create the human-readable exact-hash approval challenge."""

    release_hash = _require_text(release.get("releaseHash"), "release_hash_missing")
    payload: dict[str, Any] = {
        "schemaVersion": "exact_release_approval_request_v1",
        "releaseId": release.get("releaseId"),
        "candidateId": release.get("candidateId"),
        "candidateHash": release.get("candidateHash"),
        "releaseHash": release_hash,
        "status": "blocked_waiting_exact_release_approval",
        "approvalChallenge": f"APPROVE_DEMO_RELEASE {release_hash}",
        "approved": False,
        "demoArm": False,
        "orderCount": 0,
    }
    payload["approvalRequestHash"] = stable_hash(
        payload, prefix="exact_release_approval_request"
    )
    return payload


def validate_exact_release_approval(
    *, release: Mapping[str, Any], supplied_release_hash: str
) -> bool:
    """Validate only the exact hash; this function never mutates or executes."""

    expected = str(release.get("releaseHash") or "")
    supplied = str(supplied_release_hash or "")
    return bool(expected) and hmac.compare_digest(expected, supplied)
