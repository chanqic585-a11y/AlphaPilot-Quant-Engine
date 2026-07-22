"""Zero-budget handoff from Development selection to Formal readiness."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.standard_replication.tsmom_engine import SELECTED_TSMOM_TRIALS
from alphapilot.standard_replication.tsmom_formal_readiness import (
    build_tsmom_formal_readiness,
)

from .contracts import V36ContractError


ReadinessBuilder = Callable[..., Mapping[str, object]]

_ZERO_COUNTERS = (
    "formalRunCount",
    "formalInputReadCount",
    "resultReadCount",
    "lockedOosAccessCount",
    "releaseCount",
    "approvalCount",
    "orderCount",
)


def _required_text(value: object, *, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise V36ContractError(f"{name}_missing")
    return normalized


def _eligible_selections(
    *,
    preregistration: Mapping[str, object],
    selections: Sequence[Mapping[str, object]],
) -> list[dict[str, str]]:
    trials_by_candidate = preregistration.get("trialsByCandidate")
    if not isinstance(trials_by_candidate, Mapping):
        raise V36ContractError("preregistered_trials_missing")

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for selection in selections:
        if not bool(selection.get("eligible")):
            continue
        if int(selection.get("lockedOosReadCount") or 0) != 0:
            raise V36ContractError("locked_oos_read_before_formal")
        candidate_id = _required_text(
            selection.get("candidateId"), name="candidate_id"
        )
        trial_id = _required_text(
            selection.get("selectedTrialId"), name="selected_trial_id"
        )
        if candidate_id in seen:
            raise V36ContractError("duplicate_formal_handoff_candidate")
        seen.add(candidate_id)
        frozen_trials = trials_by_candidate.get(candidate_id)
        if not isinstance(frozen_trials, Sequence):
            raise V36ContractError("formal_handoff_candidate_not_preregistered")
        frozen_trial_ids = {
            str(trial.get("trialId") or "")
            for trial in frozen_trials
            if isinstance(trial, Mapping)
        }
        if trial_id not in frozen_trial_ids:
            raise V36ContractError("formal_handoff_trial_not_preregistered")
        result.append({"candidateId": candidate_id, "selectedTrialId": trial_id})
    return result


def _assert_zero_budget(readiness_report: Mapping[str, object]) -> None:
    for field in _ZERO_COUNTERS:
        if int(readiness_report.get(field) or 0) != 0:
            raise V36ContractError(f"formal_handoff_nonzero_counter:{field}")
    if bool(readiness_report.get("demoArm")):
        raise V36ContractError("formal_handoff_demo_arm_forbidden")


def build_formal_handoff_state(
    *,
    preregistration: Mapping[str, object],
    selections: Sequence[Mapping[str, object]],
    readiness_report: Mapping[str, object] | None,
) -> dict[str, Any]:
    """Build an auditable handoff without consuming Formal or locked evidence."""

    campaign_id = _required_text(
        preregistration.get("campaignId"), name="campaign_id"
    )
    selected = _eligible_selections(
        preregistration=preregistration,
        selections=selections,
    )
    if not selected:
        core: dict[str, Any] = {
            "schemaVersion": "v36_formal_handoff_v1",
            "campaignId": campaign_id,
            "status": "not_required_no_stable_candidate",
            "readinessHash": None,
            "selectedCandidateCount": 0,
            "formalReadyCandidateCount": 0,
            "blockedCandidateCount": 0,
            "readyCandidates": [],
            "blockedCandidates": [],
            "formalRunCount": 0,
            "formalInputReadCount": 0,
            "resultReadCount": 0,
            "lockedOosAccessCount": 0,
            "releaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
        }
        core["handoffHash"] = stable_hash(core, prefix="v36_formal_handoff")
        return core

    readiness_was_not_evaluated = readiness_report is None
    if readiness_report is None:
        readiness_report = {
            "campaignId": campaign_id,
            "readinessHash": None,
            "candidates": [
                {
                    **selection,
                    "status": "blocked",
                    "blockers": ["formal_readiness_not_evaluated"],
                }
                for selection in selected
            ],
        }
    _assert_zero_budget(readiness_report)
    report_campaign_id = str(readiness_report.get("campaignId") or "").strip()
    if report_campaign_id and report_campaign_id != campaign_id:
        raise V36ContractError("formal_readiness_campaign_mismatch")
    readiness_rows = readiness_report.get("candidates")
    if not isinstance(readiness_rows, Sequence):
        raise V36ContractError("formal_readiness_candidates_missing")

    readiness_by_candidate: dict[str, Mapping[str, object]] = {}
    for row in readiness_rows:
        if not isinstance(row, Mapping):
            raise V36ContractError("formal_readiness_candidate_invalid")
        candidate_id = _required_text(row.get("candidateId"), name="candidate_id")
        if candidate_id in readiness_by_candidate:
            raise V36ContractError("duplicate_formal_readiness_candidate")
        readiness_by_candidate[candidate_id] = row

    ready: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for selection in selected:
        candidate_id = selection["candidateId"]
        row = readiness_by_candidate.get(candidate_id)
        if row is None:
            row = {
                **selection,
                "status": "blocked",
                "blockers": ["formal_readiness_not_evaluated"],
            }
        if str(row.get("selectedTrialId") or "") != selection["selectedTrialId"]:
            raise V36ContractError("formal_readiness_trial_mismatch")
        status = str(row.get("status") or "").strip()
        blockers = sorted({str(value) for value in row.get("blockers") or []})
        normalized = {
            **selection,
            "readinessStatus": status,
            "blockers": blockers,
        }
        if status == "ready":
            if blockers:
                raise V36ContractError("ready_candidate_has_blockers")
            ready.append(normalized)
        elif status == "blocked":
            if not blockers:
                raise V36ContractError("blocked_candidate_without_reason")
            blocked.append(normalized)
        else:
            raise V36ContractError(f"formal_readiness_status_invalid:{status}")

    if readiness_was_not_evaluated:
        status = "awaiting_external_readiness"
    elif ready and blocked:
        status = "partially_ready_to_freeze"
    elif ready:
        status = "ready_to_freeze"
    else:
        status = "blocked_before_freeze"
    core = {
        "schemaVersion": "v36_formal_handoff_v1",
        "campaignId": campaign_id,
        "status": status,
        "readinessHash": readiness_report.get("readinessHash"),
        "selectedCandidateCount": len(selected),
        "formalReadyCandidateCount": len(ready),
        "blockedCandidateCount": len(blocked),
        "readyCandidates": ready,
        "blockedCandidates": blocked,
        "formalRunCount": 0,
        "formalInputReadCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "approvalCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    core["handoffHash"] = stable_hash(core, prefix="v36_formal_handoff")
    return core


def resolve_tsmom_formal_handoff(
    *,
    preregistration: Mapping[str, object],
    selections: Sequence[Mapping[str, object]],
    campaign_input: Mapping[str, object],
    readiness_builder: ReadinessBuilder = build_tsmom_formal_readiness,
) -> dict[str, Any]:
    """Audit supported TSMOM selections and block unsupported adapters explicitly."""

    selected = _eligible_selections(
        preregistration=preregistration,
        selections=selections,
    )
    if not selected:
        return build_formal_handoff_state(
            preregistration=preregistration,
            selections=selections,
            readiness_report=None,
        )

    supported: list[dict[str, str]] = []
    unsupported: list[dict[str, object]] = []
    for selection in selected:
        candidate_id = selection["candidateId"]
        expected_trial_id = SELECTED_TSMOM_TRIALS.get(candidate_id)
        if expected_trial_id is None:
            unsupported.append(
                {
                    **selection,
                    "status": "blocked",
                    "blockers": ["formal_adapter_unavailable"],
                }
            )
            continue
        if selection["selectedTrialId"] != expected_trial_id:
            raise V36ContractError("tsmom_selected_trial_identity_mismatch")
        supported.append(selection)

    readiness: dict[str, Any]
    if supported:
        replay = campaign_input.get("developmentReplay")
        panel = campaign_input.get("comparisonPanel")
        if not isinstance(replay, Mapping):
            raise V36ContractError("formal_handoff_development_replay_missing")
        if not isinstance(panel, Mapping):
            raise V36ContractError("formal_handoff_comparison_panel_missing")
        snapshot_value = _required_text(
            replay.get("snapshotManifestPath"), name="snapshot_manifest_path"
        )
        formal_start = _required_text(
            panel.get("developmentEnd"), name="formal_start"
        )
        snapshot_path = Path(snapshot_value).resolve()
        data_root = snapshot_path.parents[2]
        readiness = dict(
            readiness_builder(
                snapshot_manifest_path=snapshot_path,
                funding_root=(
                    data_root
                    / "_alphapilot"
                    / "canonical"
                    / "okx"
                    / "swap"
                    / "funding"
                ),
                candidate_ids=[row["candidateId"] for row in supported],
                formal_start=formal_start,
                campaign_id=_required_text(
                    campaign_input.get("campaignId"), name="campaign_id"
                ),
            )
        )
    else:
        readiness = {
            "campaignId": preregistration.get("campaignId"),
            "readinessHash": None,
            "candidates": [],
        }
    readiness["candidates"] = [
        *list(readiness.get("candidates") or []),
        *unsupported,
    ]
    return build_formal_handoff_state(
        preregistration=preregistration,
        selections=selections,
        readiness_report=readiness,
    )


__all__ = [
    "build_formal_handoff_state",
    "resolve_tsmom_formal_handoff",
]
