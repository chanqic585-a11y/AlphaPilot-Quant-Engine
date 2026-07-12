"""Fail-closed workflow stages, statuses, and transition rules."""

from __future__ import annotations


class WorkflowError(RuntimeError):
    """Base error for workflow commands."""


class WorkflowConflict(WorkflowError):
    """Raised when a command conflicts with immutable or active state."""


class WorkflowTransitionError(WorkflowError):
    """Raised when a state transition is not permitted."""


STAGE_ORDER = {
    "backtest": 10,
    "local_forward": 20,
    "demo": 30,
    "live": 40,
}

STAGE_PAGES = {
    "backtest": "strategy",
    "local_forward": "local_simulation",
    "demo": "demo",
    "live": "live",
}

STAGE_LABELS = {
    "backtest": "策略回测",
    "local_forward": "本地前向模拟",
    "demo": "Demo 模拟",
    "live": "实盘交易",
}

STATUS_LABELS = {
    "awaiting": "待运行",
    "queued": "排队中",
    "running": "运行中",
    "passed": "已通过",
    "failed": "未通过",
    "blocked": "已阻塞",
    "paused": "已暂停",
    "cancelled": "已取消",
    "retired": "已退役",
}

RETRY_DISPOSITIONS = {
    "same_version_retry",
    "new_version_required",
    "manual_review",
}

FAILURE_CATEGORIES = {
    "data_integrity",
    "strategy_performance",
    "overfitting_risk",
    "market_regime_mismatch",
    "execution_quality",
    "risk_limit",
    "exchange_operational",
    "worker_operational",
}

ALLOWED_ACTORS = {"user", "worker", "system", "recovery"}
WORKER_RESULT_ACTORS = {"worker", "system", "recovery"}

ALLOWED_TRANSITIONS = {
    "awaiting": {"queued", "cancelled"},
    "queued": {"running", "blocked", "paused", "cancelled"},
    "running": {"passed", "failed", "blocked", "paused", "cancelled"},
    "paused": {"queued", "cancelled"},
    "blocked": {"queued", "cancelled"},
    "passed": set(),
    "failed": set(),
    "cancelled": set(),
    "retired": set(),
}

TERMINAL_STATUSES = {"passed", "failed", "cancelled", "retired"}


def validate_stage(stage: str) -> None:
    if stage not in STAGE_ORDER:
        raise WorkflowTransitionError(f"unsupported_workflow_stage:{stage}")


def validate_status(status: str) -> None:
    if status not in STATUS_LABELS:
        raise WorkflowTransitionError(f"unsupported_workflow_status:{status}")


def validate_actor(actor: str) -> None:
    if actor not in ALLOWED_ACTORS:
        raise WorkflowTransitionError(f"unsupported_workflow_actor:{actor}")


def validate_transition(current_status: str, next_status: str, actor: str) -> None:
    validate_status(current_status)
    validate_status(next_status)
    validate_actor(actor)
    if next_status not in ALLOWED_TRANSITIONS[current_status]:
        raise WorkflowTransitionError(
            f"illegal_workflow_transition:{current_status}->{next_status}"
        )
    if next_status in {"passed", "failed", "blocked"} and actor not in WORKER_RESULT_ACTORS:
        raise WorkflowTransitionError(
            f"workflow_result_requires_worker_actor:{next_status}"
        )
