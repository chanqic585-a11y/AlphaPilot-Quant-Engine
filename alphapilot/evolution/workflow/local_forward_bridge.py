"""Read-only compatibility boundary for the retired local-forward workflow."""

from __future__ import annotations

from typing import Any, NoReturn


class LocalForwardRetiredError(RuntimeError):
    """Raised before any retired local-forward write or market operation."""


def project_legacy_local_forward(value: dict[str, Any]) -> dict[str, Any]:
    """Expose a historical local-forward record without rewriting it."""

    return {
        **value,
        "stage": "legacy_local_observation",
        "legacyStage": value.get("stage"),
        "readOnly": True,
        "deprecated": True,
        "historicalDataPreserved": True,
        "evidenceSource": "legacy_local_observation",
    }


def run_local_forward_cycle(
    workflow: Any,
    registry: Any,
    workflow_run_id: str,
    *,
    code_commit: str,
    market_data: Any,
) -> NoReturn:
    """Reject continuation of a retired local-forward run."""

    del workflow, registry, workflow_run_id, code_commit, market_data
    raise LocalForwardRetiredError("local_forward_retired")


def start_local_forward_after_pass(
    workflow: Any,
    registry: Any,
    strategy_version: Any,
    backtest_run: Any,
    evaluation_binding: Any,
    code_commit: str,
    market_data: Any,
) -> NoReturn:
    """Reject creation of a new local-forward run."""

    del (
        workflow,
        registry,
        strategy_version,
        backtest_run,
        evaluation_binding,
        code_commit,
        market_data,
    )
    raise LocalForwardRetiredError("local_forward_retired")
