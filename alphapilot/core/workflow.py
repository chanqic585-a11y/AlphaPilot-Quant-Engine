"""Workflow state machine skeleton for future controlled execution."""

WORKFLOW_STEPS = [
    "data_ingested",
    "research_summary_ready",
    "model_analysis_ready",
    "proposal_created",
    "risk_gate_pending",
    "risk_gate_approved",
    "risk_gate_rejected",
    "human_confirm_pending",
    "human_confirm_approved",
    "human_confirm_rejected",
    "broker_preflight_pending",
    "broker_preflight_ready",
    "paper_order_submitted",
    "live_order_submitted",
    "order_confirmed",
    "protective_order_verified",
    "reconciliation_done",
    "audit_complete",
    "cancelled",
    "failed",
]

TERMINAL_STATES = [
    "risk_gate_rejected",
    "human_confirm_rejected",
    "audit_complete",
    "cancelled",
    "failed",
]

_ALLOWED_TRANSITIONS = {
    "data_ingested": {"research_summary_ready", "cancelled", "failed"},
    "research_summary_ready": {"model_analysis_ready", "proposal_created", "cancelled", "failed"},
    "model_analysis_ready": {"proposal_created", "cancelled", "failed"},
    "proposal_created": {"risk_gate_pending", "cancelled", "failed"},
    "risk_gate_pending": {"risk_gate_approved", "risk_gate_rejected", "failed"},
    "risk_gate_approved": {"human_confirm_pending", "audit_complete", "cancelled"},
    "human_confirm_pending": {"human_confirm_approved", "human_confirm_rejected", "cancelled"},
    "human_confirm_approved": {"broker_preflight_pending", "audit_complete"},
    "broker_preflight_pending": {"broker_preflight_ready", "failed"},
    "broker_preflight_ready": {"paper_order_submitted", "live_order_submitted", "cancelled"},
    "paper_order_submitted": {"order_confirmed", "failed"},
    "live_order_submitted": {"order_confirmed", "failed"},
    "order_confirmed": {"protective_order_verified", "failed"},
    "protective_order_verified": {"reconciliation_done", "failed"},
    "reconciliation_done": {"audit_complete", "failed"},
}


def is_valid_workflow_step(step: str) -> bool:
    return step in WORKFLOW_STEPS


def can_transition(from_step: str, to_step: str) -> bool:
    if not is_valid_workflow_step(from_step) or not is_valid_workflow_step(to_step):
        return False
    if from_step in TERMINAL_STATES:
        return False
    return to_step in _ALLOWED_TRANSITIONS.get(from_step, set())
