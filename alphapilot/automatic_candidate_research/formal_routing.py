"""Fail-closed routing from formal validation outcomes to immutable releases."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash

from .contracts import FORMAL_OUTCOMES, RELEASE_ELIGIBLE_OUTCOMES, V36ContractError


def _required_text(value: object, *, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise V36ContractError(f"{name}_missing")
    return normalized


def route_formal_outcomes(
    *,
    preregistration: Mapping[str, object],
    selections: Sequence[Mapping[str, object]],
    formal_outcomes: Sequence[Mapping[str, object]],
) -> dict[str, Any]:
    """Route precomputed formal evidence without reimplementing formal statistics."""

    campaign_id = _required_text(preregistration.get("campaignId"), name="campaign_id")
    preregistration_hash = _required_text(
        preregistration.get("preregistrationHash"), name="preregistration_hash"
    )
    panel_hash = _required_text(
        preregistration.get("comparisonPanelHash"), name="comparison_panel_hash"
    )
    blocked_family_ids = sorted(
        str(value) for value in preregistration.get("blockedFamilyIds", [])
    )
    trials_by_candidate = preregistration.get("trialsByCandidate")
    if not isinstance(trials_by_candidate, Mapping):
        raise V36ContractError("preregistered_trials_missing")
    preregistered_trials = {
        (str(candidate_id), str(trial.get("trialId") or ""))
        for candidate_id, trials in trials_by_candidate.items()
        for trial in trials
        if isinstance(trial, Mapping) and trial.get("trialId")
    }
    selected_trials: set[tuple[str, str]] = set()
    for selection in selections:
        if not bool(selection.get("eligible")):
            continue
        if int(selection.get("lockedOosReadCount", 0)) != 0:
            raise V36ContractError("locked_oos_read_before_formal")
        selected_trial = (
            _required_text(selection.get("candidateId"), name="candidate_id"),
            _required_text(selection.get("selectedTrialId"), name="selected_trial_id"),
        )
        if selected_trial not in preregistered_trials:
            raise V36ContractError("formal_trial_not_preregistered")
        selected_trials.add(selected_trial)

    releases: list[dict[str, object]] = []
    disposition_counts = {outcome: 0 for outcome in sorted(FORMAL_OUTCOMES)}
    locked_oos_read_count = 0
    normalized_outcomes: list[dict[str, object]] = []
    seen_formal_trials: set[tuple[str, str]] = set()
    for record in formal_outcomes:
        candidate_id = _required_text(record.get("candidateId"), name="candidate_id")
        trial_id = _required_text(record.get("trialId"), name="trial_id")
        formal_trial = (candidate_id, trial_id)
        if formal_trial in seen_formal_trials:
            raise V36ContractError("duplicate_formal_outcome")
        seen_formal_trials.add(formal_trial)
        if (candidate_id, trial_id) not in selected_trials:
            raise V36ContractError("formal_trial_not_selected")
        if record.get("comparisonPanelHash") != panel_hash:
            raise V36ContractError("comparison_panel_identity_mismatch")
        outcome = _required_text(record.get("outcome"), name="outcome")
        if outcome not in FORMAL_OUTCOMES:
            raise V36ContractError(f"unsupported_formal_outcome:{outcome}")
        locked_reads = int(record.get("lockedOosReadCount", 0))
        if locked_reads < 0:
            raise V36ContractError("invalid_locked_oos_read_count")
        locked_oos_read_count += locked_reads
        disposition_counts[outcome] += 1
        normalized = dict(record)
        normalized_outcomes.append(normalized)

        if outcome not in RELEASE_ELIGIBLE_OUTCOMES:
            continue
        release_core: dict[str, object] = {
            "schemaVersion": "v36_immutable_release_ready_v1",
            "campaignId": campaign_id,
            "candidateId": candidate_id,
            "trialId": trial_id,
            "outcome": outcome,
            "preregistrationHash": preregistration_hash,
            "comparisonPanelHash": panel_hash,
            "formalArtifactHash": _required_text(
                record.get("formalArtifactHash"), name="formal_artifact_hash"
            ),
            "approved": False,
            "demoArm": False,
            "orders": 0,
        }
        release_core["immutableReleaseHash"] = stable_hash(
            release_core, prefix="v36_immutable_release"
        )
        releases.append(release_core)

    if releases:
        status = "immutable_release_ready"
    elif not formal_outcomes and selected_trials:
        status = "awaiting_formal_validation"
    elif not formal_outcomes and blocked_family_ids:
        status = "research_blocked_data"
    else:
        status = "research_zero_qualified"

    return {
        "schemaVersion": "v36_formal_route_v1",
        "campaignId": campaign_id,
        "status": status,
        "blockedFamilyIds": blocked_family_ids,
        "formalOutcomes": normalized_outcomes,
        "formalOutcomeCounts": disposition_counts,
        "formalRunCount": len(formal_outcomes),
        "resultReadCount": len(formal_outcomes),
        "lockedOosReadCount": locked_oos_read_count,
        "immutableReleases": releases,
        "releaseCount": len(releases),
        "approvalCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
