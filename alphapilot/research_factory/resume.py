"""Compact operator-facing resume report for automatic research programs."""

from __future__ import annotations

from typing import Any

from alphapilot.research_factory.program_state import ProgramStateStore


def build_resume_report(store: ProgramStateStore) -> dict[str, Any]:
    state = store.load()
    return {
        "programId": state.program_id,
        "previousCheckpoint": state.previous_checkpoint,
        "nextAllowedStage": state.next_allowed_stage,
        "oneShotClaimsConsumed": state.one_shot_claims_consumed,
        "resultReadCount": state.result_read_count,
        "stage": state.stage,
        "terminalRoute": state.terminal_route,
    }
