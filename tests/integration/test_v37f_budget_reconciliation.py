from __future__ import annotations

import json
from pathlib import Path

from alphapilot.integration.v37f_budget_reconciliation import reconcile_budget


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_reconcile_budget_inherits_without_reset_and_counts_distinct_work(
    tmp_path: Path,
) -> None:
    root = tmp_path
    inherited = Path("inherited.json")
    development = [Path("dev-a.json"), Path("dev-b.json")]
    full = [Path("full.json")]
    formal = [Path("formal-a.json"), Path("formal-b.json")]
    files = {
        inherited: {
            "budgetReset": False,
            "maximumAdditionalFullBacktests": 96,
            "fullBacktestsUsed": 0,
            "fullBacktestsRemaining": 96,
        },
        development[0]: {"trialCount": 18},
        development[1]: {"trialCount": 6},
        full[0]: {"campaignSummary": {"fullBacktestCount": 1}},
        formal[0]: {"attemptCount": 1, "state": "completed"},
        formal[1]: {"attemptCount": 2, "state": "failed"},
    }
    for relative, payload in files.items():
        _write(root / relative, payload)

    result = reconcile_budget(
        root=root,
        inherited_budget_path=inherited,
        development_summary_paths=development,
        full_backtest_evidence_paths=full,
        formal_ledger_paths=formal,
    )

    assert result["budgetReset"] is False
    assert result["developmentTrialsUsed"] == 24
    assert result["fullBacktestsUsed"] == 1
    assert result["formalRunsUsed"] == 3
    assert result["formalRunsCompleted"] == 1
    assert result["remainingByAuthoritativePolicy"] == {
        "developmentTrials": {
            "value": None,
            "status": "unbounded_by_current_authority",
        },
        "fullBacktests": {"value": 95, "status": "bounded"},
        "formalRuns": {
            "value": None,
            "status": "unbounded_by_current_authority",
        },
    }
    assert len(result["sourceEvidence"]) == 6
    assert all(row["sha256"] for row in result["sourceEvidence"])


def test_reconcile_budget_rejects_reset_or_inconsistent_inherited_budget(
    tmp_path: Path,
) -> None:
    root = tmp_path
    inherited = Path("inherited.json")
    _write(
        root / inherited,
        {
            "budgetReset": True,
            "maximumAdditionalFullBacktests": 96,
            "fullBacktestsUsed": 0,
            "fullBacktestsRemaining": 96,
        },
    )

    try:
        reconcile_budget(
            root=root,
            inherited_budget_path=inherited,
            development_summary_paths=[],
            full_backtest_evidence_paths=[],
            formal_ledger_paths=[],
        )
    except ValueError as exc:
        assert "budget reset" in str(exc).lower()
    else:
        raise AssertionError("budget reset must be rejected")
