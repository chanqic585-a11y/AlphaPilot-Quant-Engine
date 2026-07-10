"""Fail-closed Demo promotion, monitoring, and rollback contracts."""

from .demo_release import DEFAULT_DEMO_RISK_ENVELOPE, promote_candidate_to_demo
from .drift_monitor import DemoDriftObservation, evaluate_demo_drift
from .gate import PromotionEvidence, evaluate_demo_promotion
from .live_candidate import (
    DemoValidationEvidence,
    LiveRiskBudgetProposal,
    build_live_candidate_package,
)
from .rollback import decide_demo_rollback

__all__ = [
    "DEFAULT_DEMO_RISK_ENVELOPE",
    "DemoDriftObservation",
    "PromotionEvidence",
    "DemoValidationEvidence",
    "LiveRiskBudgetProposal",
    "build_live_candidate_package",
    "decide_demo_rollback",
    "evaluate_demo_drift",
    "evaluate_demo_promotion",
    "promote_candidate_to_demo",
]
