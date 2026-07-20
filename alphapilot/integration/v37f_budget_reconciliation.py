"""Reconcile inherited V33-V37 research budgets without resetting history."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from alphapilot.evolution.registry.hashing import sha256_file


def _load(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    return json.loads(path.read_text(encoding="utf-8"))


def _evidence_row(
    root: Path,
    relative: Path,
    *,
    category: str,
    contribution: int,
) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative.as_posix(),
        "sha256": sha256_file(path),
        "category": category,
        "contribution": int(contribution),
    }


def _development_trial_count(payload: dict[str, Any]) -> int:
    return int(payload.get("trialCount") or 0)


def _full_backtest_count(payload: dict[str, Any]) -> int:
    summary = payload.get("campaignSummary") or {}
    return int(payload.get("fullBacktestCount") or summary.get("fullBacktestCount") or 0)


def _formal_attempt_count(payload: dict[str, Any]) -> int:
    return int(payload.get("attemptCount") or 0)


def reconcile_budget(
    *,
    root: Path,
    inherited_budget_path: Path,
    development_summary_paths: Iterable[Path],
    full_backtest_evidence_paths: Iterable[Path],
    formal_ledger_paths: Iterable[Path],
) -> dict[str, Any]:
    """Return an auditable inherited budget ledger with no invented limits."""

    root = Path(root)
    inherited = _load(root, inherited_budget_path)
    if inherited.get("budgetReset") is not False:
        raise ValueError("Inherited budget reset is forbidden")

    maximum_full = int(inherited["maximumAdditionalFullBacktests"])
    inherited_used = int(inherited.get("fullBacktestsUsed") or 0)
    inherited_remaining = int(inherited.get("fullBacktestsRemaining") or 0)
    if inherited_remaining != maximum_full - inherited_used:
        raise ValueError("Inherited full-backtest budget is inconsistent")

    evidence = [
        _evidence_row(
            root,
            inherited_budget_path,
            category="inherited_budget",
            contribution=inherited_used,
        )
    ]

    development_used = 0
    for relative in development_summary_paths:
        count = _development_trial_count(_load(root, relative))
        development_used += count
        evidence.append(
            _evidence_row(
                root,
                relative,
                category="development_trial",
                contribution=count,
            )
        )

    new_full_backtests = 0
    for relative in full_backtest_evidence_paths:
        count = _full_backtest_count(_load(root, relative))
        new_full_backtests += count
        evidence.append(
            _evidence_row(
                root,
                relative,
                category="full_backtest",
                contribution=count,
            )
        )

    formal_runs = 0
    formal_completed = 0
    for relative in formal_ledger_paths:
        payload = _load(root, relative)
        count = _formal_attempt_count(payload)
        formal_runs += count
        if payload.get("state") == "completed":
            formal_completed += count
        evidence.append(
            _evidence_row(
                root,
                relative,
                category="formal_run",
                contribution=count,
            )
        )

    full_backtests_used = inherited_used + new_full_backtests
    full_remaining = maximum_full - full_backtests_used
    if full_remaining < 0:
        raise ValueError("Full-backtest budget is exhausted")

    unbounded = {"value": None, "status": "unbounded_by_current_authority"}
    return {
        "schemaVersion": "alphapilot_v37f_budget_reconciliation_v1",
        "budgetReset": False,
        "developmentTrialsUsed": development_used,
        "fullBacktestsUsed": full_backtests_used,
        "formalRunsUsed": formal_runs,
        "formalRunsCompleted": formal_completed,
        "remainingByAuthoritativePolicy": {
            "developmentTrials": dict(unbounded),
            "fullBacktests": {"value": full_remaining, "status": "bounded"},
            "formalRuns": dict(unbounded),
        },
        "inheritedPolicy": {
            "maximumAdditionalFullBacktests": maximum_full,
            "inheritedFullBacktestsUsed": inherited_used,
            "inheritedFullBacktestsRemaining": inherited_remaining,
        },
        "sourceEvidence": evidence,
    }
