"""Deterministic V36 trial preregistration over the V35 source registry."""

from __future__ import annotations

from typing import Any, Mapping

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.standard_replication import ReplicationSourceRegistry

from .contracts import (
    BLOCKED_REPLICATION_STATES,
    COMPARISON_PANEL_FIELDS,
    ELIGIBLE_REPLICATION_STATES,
    FAMILY_STRATEGY_TYPES,
    TRIAL_SCALES,
)


def _required_text(value: object, *, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{name}_missing")
    return normalized


def _freeze_panel(
    *,
    comparison_panel: Mapping[str, object],
    candidate_ids: list[str],
    trial_ids: list[str],
) -> dict[str, object]:
    frozen: dict[str, object] = {}
    for field in COMPARISON_PANEL_FIELDS:
        if field not in comparison_panel or comparison_panel[field] in {None, ""}:
            raise ValueError(f"comparison_panel_incomplete:{field}")
        frozen[field] = comparison_panel[field]
    frozen["candidateIds"] = list(candidate_ids)
    frozen["trialIds"] = list(trial_ids)
    return frozen


def build_preregistration(
    *,
    registry: ReplicationSourceRegistry,
    campaign_id: str,
    created_at: str,
    comparison_panel: Mapping[str, object],
) -> dict[str, Any]:
    """Freeze finite neighborhoods without reading Development or Locked OOS."""

    normalized_campaign_id = _required_text(campaign_id, name="campaign_id")
    normalized_created_at = _required_text(created_at, name="created_at")
    candidate_ids = sorted(
        variant.candidate_id
        for family in registry.items
        for variant in family.variants
    )
    blocked_family_ids = sorted(
        family.family_id
        for family in registry.items
        if family.replication_state in BLOCKED_REPLICATION_STATES
    )
    context_only_candidate_ids = sorted(
        variant.candidate_id
        for family in registry.items
        if family.replication_state == "registered_context_only"
        for variant in family.variants
    )

    trials_by_candidate: dict[str, list[dict[str, object]]] = {}
    for family in sorted(registry.items, key=lambda item: item.family_id):
        if family.replication_state not in ELIGIBLE_REPLICATION_STATES:
            continue
        strategy_type = FAMILY_STRATEGY_TYPES[family.family_id]
        for variant in sorted(family.variants, key=lambda item: item.candidate_id):
            trials: list[dict[str, object]] = []
            for index, scale in enumerate(TRIAL_SCALES):
                trial_core = {
                    "candidateId": variant.candidate_id,
                    "familyId": family.family_id,
                    "strategyType": strategy_type,
                    "trialIndex": index,
                    "neighborhoodOffset": index - 1,
                    "parameterScale": scale,
                    "baseParameters": dict(family.parameters),
                }
                trial_core["trialId"] = stable_hash(
                    trial_core,
                    prefix="v36_trial",
                )
                trials.append(trial_core)
            trials_by_candidate[variant.candidate_id] = trials

    trial_ids = sorted(
        str(trial["trialId"])
        for trials in trials_by_candidate.values()
        for trial in trials
    )
    frozen_panel = _freeze_panel(
        comparison_panel=comparison_panel,
        candidate_ids=candidate_ids,
        trial_ids=trial_ids,
    )
    panel_hash = stable_hash(frozen_panel, prefix="v36_comparison_panel")
    payload: dict[str, Any] = {
        "schemaVersion": "v36_candidate_preregistration_v1",
        "campaignId": normalized_campaign_id,
        "createdAt": normalized_created_at,
        "sourceRegistryId": registry.registry_id,
        "candidateIds": candidate_ids,
        "candidateCount": len(candidate_ids),
        "eligibleCandidateIds": sorted(trials_by_candidate),
        "eligibleCandidateCount": len(trials_by_candidate),
        "blockedFamilyIds": blocked_family_ids,
        "blockedFamilyCount": len(blocked_family_ids),
        "contextOnlyCandidateIds": context_only_candidate_ids,
        "trialsByCandidate": trials_by_candidate,
        "trialCount": len(trial_ids),
        "comparisonPanel": frozen_panel,
        "comparisonPanelHash": panel_hash,
        "selectionSplit": "development",
        "lockedOosReadCount": 0,
    }
    payload["preregistrationHash"] = stable_hash(
        payload,
        prefix="v36_preregistration",
    )
    return payload
