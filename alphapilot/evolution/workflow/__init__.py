"""Public API for the V13.27 auditable strategy workflow."""

from .backtest import (
    BacktestAdapterError,
    BacktestAdapterResult,
    execute_registered_adapter,
    run_backtest_workflow,
)
from .bootstrap import (
    DEFAULT_BACKTEST_GATE_RULES,
    ensure_default_backtest_gate_profile,
    register_alpha191_observer,
)
from .projection import build_workflow_projection
from .repository import WorkflowRepository
from .service import (
    archive_strategy_version,
    cancel_workflow_run,
    checkpoint_workflow_run,
    complete_workflow_run,
    create_challenger_version,
    create_next_stage_run,
    pause_workflow_run,
    queue_workflow_run,
    register_strategy_version,
    retry_workflow_run,
    start_workflow_run,
)
from .states import WorkflowConflict, WorkflowError, WorkflowTransitionError
from .types import (
    FailureDiagnosisRecord,
    GateProfileRecord,
    StageEventRecord,
    StrategyVersionRecord,
    WorkflowRunRecord,
)

__all__ = [
    "BacktestAdapterError",
    "BacktestAdapterResult",
    "DEFAULT_BACKTEST_GATE_RULES",
    "FailureDiagnosisRecord",
    "GateProfileRecord",
    "StageEventRecord",
    "StrategyVersionRecord",
    "WorkflowConflict",
    "WorkflowError",
    "WorkflowRepository",
    "WorkflowRunRecord",
    "WorkflowTransitionError",
    "archive_strategy_version",
    "build_workflow_projection",
    "cancel_workflow_run",
    "checkpoint_workflow_run",
    "complete_workflow_run",
    "create_challenger_version",
    "create_next_stage_run",
    "ensure_default_backtest_gate_profile",
    "execute_registered_adapter",
    "pause_workflow_run",
    "queue_workflow_run",
    "register_alpha191_observer",
    "register_strategy_version",
    "retry_workflow_run",
    "run_backtest_workflow",
    "start_workflow_run",
]
