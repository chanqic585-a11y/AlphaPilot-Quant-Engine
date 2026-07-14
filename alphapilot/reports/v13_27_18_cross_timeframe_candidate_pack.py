"""Bind V13.27.18 executable definitions to prior development evidence."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.workflow.data_contract import timeframe_plan
from alphapilot.short_cycle.workflow_candidates import ShortCycleWorkflowCandidate


_EVIDENCE_CANDIDATE_IDS = {
    "event_4h_bull_recovery_atr15_h24_v1": "v13_27_17_4h_bull_reclaim_atr15_h24",
    "event_4h_bull_recovery_atr18_h24_v1": "v13_27_17_4h_bull_reclaim_atr18_h24",
    "event_4h_bull_recovery_atr20_h24_v1": "v13_27_17_4h_bull_reclaim_atr20_h24",
    "event_4h_bull_recovery_atr20_h30_v1": "v13_27_17_4h_bull_reclaim_atr20_h30",
    "event_4h_bull_recovery_atr20_h36_v1": "v13_27_17_4h_bull_reclaim_atr20_h36",
    "event_1d_breakout_retest_atr20_v1": "v13_27_17_1d_breakout_atr20",
    "event_1d_squeeze_breakout_atr20_v1": "v13_27_17_1d_squeeze_breakout_atr20",
    "event_1d_broad_squeeze_breakout_atr20_v1": "v13_27_17_1d_broad_squeeze_breakout_atr20",
    "event_1d_oversold_sweep_reclaim_atr12_v1": "v13_27_17_1d_oversold_reclaim_atr12",
    "event_1d_oversold_sweep_reclaim_atr10_v1": "v13_27_17_1d_oversold_reclaim_atr10",
}


def evidence_candidate_id(candidate: ShortCycleWorkflowCandidate) -> str:
    return _EVIDENCE_CANDIDATE_IDS.get(candidate.familyKey, candidate.familyKey)


def build_v13_27_18_candidate_rows(
    candidates: Sequence[ShortCycleWorkflowCandidate],
    source_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    source_by_id = {
        str(item.get("candidateId") or ""): dict(item) for item in source_rows
    }
    if len(source_by_id) != len(source_rows) or "" in source_by_id:
        raise ValueError("candidate_evidence_identity_invalid")

    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        source_id = evidence_candidate_id(candidate)
        source = source_by_id.get(source_id)
        if source is None:
            raise ValueError(f"candidate_evidence_missing:{source_id}")
        definition = candidate.definition()
        metadata = dict(definition.get("researchMetadata") or {})
        formal_data_plan = dict(
            definition.get("formalDataPlan") or timeframe_plan(candidate.timeframe)
        )
        row = dict(source)
        row.pop("workflowBlocker", None)
        row.update(
            {
                "candidateId": candidate.familyKey,
                "displayName": candidate.displayName,
                "timeframe": candidate.timeframe,
                "family": candidate.signalFamily,
                "direction": candidate.direction,
                "targetR": float(definition["targetR"]),
                "parameters": dict(candidate.parameters),
                "selectionTier": str(metadata["selectionTier"]),
                "evidenceSourceCandidateId": source_id,
                "evidenceLineage": list(metadata.get("evidenceLineage") or []),
                "researchEvidenceStatus": str(metadata.get("evidenceStatus") or ""),
                "formalDataPlan": formal_data_plan,
                "definitionHash": stable_hash(
                    definition,
                    prefix="v13_27_18_strategy_definition",
                ),
                "directCandidateBacktestCompleted": bool(
                    source.get("directCandidateBacktestCompleted", True)
                ),
                "executableWorkflowAvailable": True,
                "formalPromotionEvidence": False,
                "lockedOrHoldoutUsedForSelection": False,
                "researchOnly": True,
                "executionEnabled": False,
            }
        )
        rows.append(row)
    return rows
