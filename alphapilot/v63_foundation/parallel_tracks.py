"""Deterministic artifacts for the V63 bounded parallel research tracks."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Mapping

from alphapilot.evolution.registry.hashing import stable_hash

V62_FAILED_CANDIDATE_IDS = frozenset(
    {
        "v35_pair_rv_crypto_adaptation",
        "v35_pair_rv_source_replication",
        "v35_tsmom_crypto_adaptation",
        "v35_tsmom_source_replication",
    }
)

_TRACK_B_FAMILIES: tuple[dict[str, object], ...] = (
    {
        "familyId": "v63_participation_shock_recovery_1h",
        "hypothesisId": "v63_hypothesis_participation_shock_recovery",
        "hypothesis": (
            "After a broad participation shock, liquid contracts whose close "
            "location and relative volume recover faster than market breadth "
            "may exhibit a bounded 1h continuation window."
        ),
        "timeframe": "1h",
        "direction": "long_or_flat",
        "requiredInputs": ["ohlcv", "btc_reference_ohlcv", "pit_universe"],
        "variants": ["conservative", "balanced"],
    },
    {
        "familyId": "v63_breadth_diffusion_lag_4h",
        "hypothesisId": "v63_hypothesis_breadth_diffusion_lag",
        "hypothesis": (
            "A market breadth inflection may propagate from the most liquid "
            "contracts to second-tier liquid contracts with a bounded 4h lag."
        ),
        "timeframe": "4h",
        "direction": "long_short_or_flat",
        "requiredInputs": ["ohlcv", "btc_reference_ohlcv", "pit_universe"],
        "variants": ["low_turnover", "balanced"],
    },
    {
        "familyId": "v63_volatility_exhaustion_recovery_15m",
        "hypothesisId": "v63_hypothesis_volatility_exhaustion_recovery",
        "hypothesis": (
            "Following a cross-sectional volatility burst and failed price "
            "continuation, contracts with improving close location may show a "
            "short-lived 15m exhaustion recovery."
        ),
        "timeframe": "15m",
        "direction": "long_short_or_flat",
        "requiredInputs": ["ohlcv", "btc_reference_ohlcv", "pit_universe"],
        "variants": ["strict_liquidity", "balanced"],
    },
)

_TRACK_C_CHECKS = (
    "coverage",
    "security_findings",
    "factor_bench",
    "qlib",
    "observer",
    "deployment_scripts",
)
_TRACK_C_STATUSES = frozenset({"passed", "blocked", "not_run"})
_SAFE_ARTIFACT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _required_text(value: object, *, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{name}_missing")
    return normalized


def build_track_b_campaign(
    *,
    campaign_id: str,
    created_at: str,
    data_snapshot_id: str,
    candidate_id_override: str | None = None,
) -> dict[str, object]:
    """Freeze a fresh, bounded Development-only campaign without running it."""

    campaign_id = _required_text(campaign_id, name="campaign_id")
    created_at = _required_text(created_at, name="created_at")
    data_snapshot_id = _required_text(data_snapshot_id, name="data_snapshot_id")
    families = deepcopy(list(_TRACK_B_FAMILIES))
    candidate_ids: list[str] = []
    for family in families:
        family_id = str(family["familyId"])
        variants = list(family.pop("variants"))
        family_candidates = [
            f"{family_id}_{variant}_v1" for variant in variants
        ]
        family["candidateIds"] = family_candidates
        candidate_ids.extend(family_candidates)

    if candidate_id_override is not None:
        candidate_ids[0] = _required_text(
            candidate_id_override,
            name="candidate_id_override",
        )
        families[0]["candidateIds"][0] = candidate_ids[0]
    reused = sorted(set(candidate_ids) & V62_FAILED_CANDIDATE_IDS)
    if reused:
        raise ValueError(
            "v62_failed_candidate_identity_reused:" + ",".join(reused)
        )

    payload: dict[str, object] = {
        "schemaVersion": "alphapilot_v63_track_b_preregistration_v1",
        "campaignId": campaign_id,
        "createdAt": created_at,
        "status": "preregistered_dry_preparation_only",
        "selectionSplit": "development",
        "dataSnapshotId": data_snapshot_id,
        "lockedOosReadCount": 0,
        "sourceCandidateIds": [],
        "excludedCandidateIds": sorted(V62_FAILED_CANDIDATE_IDS),
        "families": families,
        "candidateIds": candidate_ids,
        "budget": {
            "maximumFamilies": 3,
            "maximumCandidates": 6,
            "maximumConcurrentCampaigns": 1,
            "formalRunBudget": 0,
        },
        "safety": {
            "releaseApprovalAllowed": False,
            "armAllowed": False,
            "orderCapabilityEnabled": False,
            "liveAllowed": False,
            "withdrawAllowed": False,
        },
        "releaseApprovalAllowed": False,
        "armAllowed": False,
        "orderCapabilityEnabled": False,
        "formalRunCount": 0,
        "resultReadCount": 0,
    }
    payload["preregistrationHash"] = stable_hash(
        payload,
        prefix="v63_track_b_preregistration",
    )
    return payload


def build_track_c_status_matrix(
    *,
    checks: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Build an honest Track C status matrix from explicit check receipts."""

    missing = sorted(set(_TRACK_C_CHECKS) - set(checks))
    unexpected = sorted(set(checks) - set(_TRACK_C_CHECKS))
    if missing:
        raise ValueError("track_c_checks_missing:" + ",".join(missing))
    if unexpected:
        raise ValueError("track_c_checks_unexpected:" + ",".join(unexpected))

    normalized: dict[str, dict[str, object]] = {}
    counts = {"passed": 0, "blocked": 0, "not_run": 0}
    for name in _TRACK_C_CHECKS:
        receipt = deepcopy(dict(checks[name]))
        status = str(receipt.get("status") or "").strip()
        if status not in _TRACK_C_STATUSES:
            raise ValueError(f"track_c_status_invalid:{name}:{status}")
        if status != "passed" and not str(receipt.get("reason") or "").strip():
            raise ValueError(f"track_c_reason_missing:{name}")
        receipt["status"] = status
        normalized[name] = receipt
        counts[status] += 1

    payload: dict[str, object] = {
        "schemaVersion": "alphapilot_v63_track_c_status_matrix_v1",
        "overallStatus": (
            "completed"
            if counts["blocked"] == 0 and counts["not_run"] == 0
            else "completed_with_blockers"
        ),
        "checks": normalized,
        "counts": counts,
        "demoArmAllowed": False,
        "liveArmAllowed": False,
        "orderCapabilityEnabled": False,
        "withdrawAllowed": False,
    }
    payload["statusMatrixHash"] = stable_hash(
        payload,
        prefix="v63_track_c_status_matrix",
    )
    return payload


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    temporary_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary_path.write_bytes(encoded)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return hashlib.sha256(encoded).hexdigest()


def write_parallel_track_artifacts(
    *,
    repository_root: str | Path,
    campaign: Mapping[str, object],
    track_c_matrix: Mapping[str, object],
) -> dict[str, object]:
    """Write the frozen Track B/C receipts and their deterministic manifest."""

    root = Path(repository_root).resolve()
    campaign_id = _required_text(campaign.get("campaignId"), name="campaign_id")
    if not _SAFE_ARTIFACT_ID.fullmatch(campaign_id):
        raise ValueError("campaign_id_unsafe_for_artifact_path")

    relative_artifacts: tuple[tuple[Path, Mapping[str, object]], ...] = (
        (
            Path("research")
            / "preregistrations"
            / f"{campaign_id}.json",
            campaign,
        ),
        (
            Path("reports")
            / "v63_server_foundation"
            / "track_b_campaign_preparation.json",
            campaign,
        ),
        (
            Path("reports")
            / "v63_server_foundation"
            / "track_c_status_matrix.json",
            track_c_matrix,
        ),
    )
    artifacts: list[dict[str, object]] = []
    for relative_path, payload in relative_artifacts:
        sha256 = _atomic_write_json(root / relative_path, payload)
        artifacts.append(
            {
                "path": relative_path.as_posix(),
                "sha256": sha256,
                "sizeBytes": (root / relative_path).stat().st_size,
            }
        )

    manifest: dict[str, object] = {
        "schemaVersion": "alphapilot_v63_parallel_track_manifest_v1",
        "campaignId": campaign_id,
        "generatedAt": campaign.get("createdAt"),
        "artifactCount": len(artifacts),
        "artifacts": artifacts,
        "safety": {
            "demoArmAllowed": False,
            "liveArmAllowed": False,
            "orderCapabilityEnabled": False,
            "withdrawAllowed": False,
        },
    }
    manifest["manifestHash"] = stable_hash(
        manifest,
        prefix="v63_parallel_track_manifest",
    )
    _atomic_write_json(
        root
        / "reports"
        / "v63_server_foundation"
        / "artifact_manifest.json",
        manifest,
    )
    return manifest
