"""Metadata-only Locked OOS lineage audit.

This module intentionally refuses paths that look like holdout content. It may
inspect identity and access metadata, but it must never open holdout returns,
events, metrics, or market data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


CAMPAIGN_ID = "advisory_r_v16_correction_8ec939e8f7ce17a3d259c72c134d02"
_FORBIDDEN_COMPONENTS = {
    "holdout_content",
    "holdout_data",
    "locked_oos_content",
    "locked_oos_data",
}


def _normalized_component(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def load_metadata_json(path: Path) -> dict[str, Any]:
    """Load JSON only when its path cannot be mistaken for holdout content."""

    normalized = {_normalized_component(part) for part in Path(path).parts}
    if normalized & _FORBIDDEN_COMPONENTS:
        raise ValueError(f"Locked OOS content path is forbidden: {path}")
    if path.suffix.lower() != ".json":
        raise ValueError(f"Metadata audit accepts JSON only: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Metadata root must be an object: {path}")
    return value


def _nested_get(payload: Mapping[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value


def _contains_nonempty_key(payload: Any, keys: set[str]) -> bool:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if key in keys and value not in (None, "", [], {}):
                return True
            if _contains_nonempty_key(value, keys):
                return True
    elif isinstance(payload, list):
        return any(_contains_nonempty_key(item, keys) for item in payload)
    return False


def audit_holdout_lineage(repo_root: Path) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    campaign_root = repo_root / "reports" / "advisory_r_campaign" / CAMPAIGN_ID
    metadata_paths = {
        "preregistration": repo_root
        / "research"
        / "preregistrations"
        / f"{CAMPAIGN_ID}.json",
        "campaignSummary": campaign_root / "campaign_summary.json",
        "correctionManifest": campaign_root / "correction_manifest.json",
        "routeDecision": campaign_root / "route_decision.json",
        "prefilterResults": campaign_root / "prefilter_results.json",
    }
    metadata = {role: load_metadata_json(path) for role, path in metadata_paths.items()}
    access_counts = {
        "campaignSummary": _nested_get(metadata["campaignSummary"], "lockedOosAccessCount"),
        "correctionManifest": _nested_get(
            metadata["correctionManifest"], "safetyBoundary", "lockedOosAccessCount"
        ),
        "prefilterResults": _nested_get(
            metadata["prefilterResults"], "route", "lockedOosAccessCount"
        ),
        "preregistration": _nested_get(
            metadata["preregistration"], "safetyBoundary", "lockedOosAccessCount"
        ),
        "routeDecision": _nested_get(metadata["routeDecision"], "lockedOosAccessCount"),
    }
    counts_are_integers = all(isinstance(value, int) for value in access_counts.values())
    unique_counts = set(access_counts.values()) if counts_are_integers else set()
    counts_consistent = counts_are_integers and len(unique_counts) == 1
    recorded_access_count = next(iter(unique_counts)) if counts_consistent else None

    boundary_keys = {
        "holdoutBoundary",
        "lockedOosBoundary",
        "lockedOosStart",
        "lockedOosEnd",
    }
    hash_keys = {"holdoutHash", "lockedOosHash", "lockedOosDataHash"}
    boundary_present = any(
        _contains_nonempty_key(document, boundary_keys) for document in metadata.values()
    )
    holdout_hash_present = any(
        _contains_nonempty_key(document, hash_keys) for document in metadata.values()
    )
    ledger_candidates = (
        repo_root / "research" / "holdout_unlocks" / f"{CAMPAIGN_ID}.json",
        repo_root / "reports" / "formal_validation" / CAMPAIGN_ID / "holdout_unlock.json",
    )
    unlock_ledger_present = any(path.is_file() for path in ledger_candidates)
    clean_available = bool(
        counts_consistent
        and recorded_access_count == 0
        and boundary_present
        and holdout_hash_present
        and unlock_ledger_present
    )
    missing_identity_fields = []
    if not boundary_present:
        missing_identity_fields.append("holdoutBoundary")
    if not holdout_hash_present:
        missing_identity_fields.append("holdoutHash")

    if not counts_consistent or recorded_access_count not in (0,):
        status = "blocked"
    elif clean_available:
        status = "ready"
    else:
        status = "limitation"
    return {
        "schemaVersion": "formal_validation_holdout_lineage_audit_v1",
        "campaignId": CAMPAIGN_ID,
        "status": status,
        "metadataOnly": True,
        "metricsComputed": False,
        "contentFilesRead": [],
        "metadataFilesRead": {
            role: path.relative_to(repo_root).as_posix() for role, path in metadata_paths.items()
        },
        "accessCountSources": access_counts,
        "accessCountsConsistent": counts_consistent,
        "recordedAccessCount": recorded_access_count,
        "unlockLedgerPresent": unlock_ledger_present,
        "holdoutBoundaryPresent": boundary_present,
        "holdoutHashPresent": holdout_hash_present,
        "missingIdentityFields": missing_identity_fields,
        "cleanLockedOosAvailable": clean_available,
        "admissionRule": (
            "Locked OOS remains unavailable until a frozen boundary, content hash, and "
            "zero-access one-shot ledger are all present."
        ),
    }
