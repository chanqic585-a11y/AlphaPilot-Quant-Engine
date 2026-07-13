# AlphaPilot Bounded Optimization and Trend Exit Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `executing-plans` and complete each task with RED-GREEN-REFACTOR.

**Goal:** Add an immutable `+2R half exit + confirmed-close ATR runner` research exit, and an auditable automatic optimization loop that stops after a bounded budget instead of tuning until historical gates pass.

**Architecture:** Extend the vectorized prepared execution path with ATR14 and a separate deterministic split-exit evaluator while preserving the fixed-2R default. Formal strategy definitions opt in through an immutable `exitPolicy`. A Quant-owned bounded optimizer reads only development and walk-forward metrics, mutates allowlisted existing parameters, records immutable lineage/audit events, creates at most one active challenger per root, and stops at structural, data, formal-validation, or budget terminal states. Locked OOS remains excluded from parameter selection and no failed strategy is force-promoted.

**Tech Stack:** Python 3, pandas/numpy, SQLite evolution registry, pytest/unittest, immutable JSON evidence.

---

## Task 1: Preserve challenger gate inheritance

**Files:**
- Modify: `alphapilot/evolution/workflow/service.py`
- Modify: `tests/evolution/test_workflow_orchestrator.py`

1. Add a failing test proving a challenger inherits the parent's current backtest gate profile.
2. Implement inheritance through `register_strategy_version(... initial_gate_profile_id=...)` without mutating the parent.
3. Run the focused test and commit as `Preserve challenger backtest gate binding`.

## Task 2: Add the confirmed-close split exit evaluator

**Files:**
- Modify: `alphapilot/evolution/evaluation/fixed_r_path.py`
- Modify: `tests/evolution/test_fixed_r_path.py`

1. Add failing tests for long and short paths: full stop before target, conservative same-bar stop/target, 50% at +2R, runner stop initialized at +1R, one-way ATR tightening from confirmed closes, max-hold exit, fees/slippage/funding on weighted quantities, and invalid configuration.
2. Extend prepared paths with read-only true-range/ATR14 values calculated without lookahead.
3. Add immutable config fields `exitMode`, `firstTargetFraction`, `runnerAtrPeriod`, `runnerAtrMultiple`, and `runnerLockedR` with the current fixed exit as defaults.
4. Add result fields for first-target hit/time/price, runner exit/time/price, gross/net realized R, and weighted cost R while preserving existing result fields.
5. Implement the minimal deterministic evaluator. The runner stop becomes active only on the bar after the confirmed close that tightened it.
6. Run focused tests and commit as `Add deterministic 2R half ATR runner`.

## Task 3: Wire the exit policy into formal evidence

**Files:**
- Modify: `alphapilot/evolution/evaluation/formal_strategy_backtest.py`
- Modify: `tests/evolution/test_formal_strategy_backtest.py`

1. Add failing tests proving default strategies remain fixed-2R and an immutable `two_r_half_atr_runner_v1` definition builds the split-exit config for baseline and stress paths.
2. Reject unknown exit policies and any first target below 2R.
3. Add `exitPolicy`, first-target fraction, ATR period/multiple, and runner lock to report evidence/checks; include aggregate first-target and runner-exit counts.
4. Confirm costs and funding remain in net R and locked/holdout evidence is unchanged.
5. Run focused and full Quant tests; commit as `Wire trend runner into formal backtests`.

## Task 4: Implement the bounded optimizer as a pure policy

**Files:**
- Create: `alphapilot/evolution/workflow/bounded_optimizer.py`
- Create: `tests/evolution/test_bounded_optimizer.py`

1. Add failing tests for: data blocker stop, structural weakness stop, deterministic allowlisted mutation, `targetR >= 2` lock, no mutable parameter stop, one-active-challenger guard, budget exhaustion at three attempts, and locked/holdout metrics ignored.
2. Define terminal states: `data_evidence_blocked`, `structural_redesign_required`, `formal_validation_failed`, `budget_exhausted`, and `passed`.
3. Use only `metrics.bySplit.development` and `metrics.bySplit.walk_forward` for automatic decisions. Never inspect holdout/locked values.
4. Mutate one allowlisted existing parameter per attempt within explicit bounds; keep lineage fields in the immutable definition and return an explainable decision payload.
5. Run focused tests and commit as `Add bounded optimization policy`.

## Task 5: Persist decisions and requeue one challenger

**Files:**
- Modify: `alphapilot/evolution/workflow/cli.py`
- Modify: `alphapilot/evolution/workflow/projection.py`
- Modify: `alphapilot/evolution/registry/repositories.py`
- Modify: `tests/evolution/test_workflow_cli.py`
- Modify: `tests/evolution/test_registry_repositories.py`

1. Add failing tests showing a strategy-performance failure creates one immutable challenger, appends a redacted `bounded_auto_optimization` AuditEvent, and drains its new backtest run in the same serial batch.
2. Add failing tests proving worker/data failures do not create challengers, duplicate retries are idempotent, and terminal decisions create no version.
3. Add an AuditEvents query helper and keep decision payloads free of raw market rows or credentials.
4. Integrate the optimizer after a completed failed backtest. The serial worker remains one formal slot plus one data-prefetch slot.
5. Expose root id, attempt/max attempts, current decision, changed parameter, and terminal reason in the workflow projection.
6. Run focused tests and commit as `Automate bounded challenger requeue`.

## Task 6: Separate selection evidence from the final lock

**Files:**
- Modify: `alphapilot/evolution/evaluation/formal_strategy_backtest.py`
- Modify: `alphapilot/evolution/workflow/bounded_optimizer.py`
- Modify: `tests/evolution/test_bounded_optimizer.py`
- Modify: `tests/evolution/test_formal_strategy_backtest.py`

1. Add a failing test proving optimization decisions receive a sanitized metrics view containing only development and walk-forward splits.
2. Add a failing test proving the selected immutable challenger can run one normal full formal validation, but a failed full formal validation becomes terminal and cannot feed another attempt.
3. Implement the sanitized selection view and `formalValidationConsumed` lineage flag.
4. Keep holdout/locked reports in formal evidence, but never pass them into the mutation policy.
5. Run focused tests and commit as `Protect locked evidence from auto tuning`.

## Task 7: Documentation and full validation

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-07-14-bounded-auto-optimization-trend-runner-demo-diagnostics-design.md` only if implementation differs, with an explicit deviation note.

1. Document R semantics, the possible +1.5R gross complete trade after the half exit, bounded optimization terminal states, and no-force-pass boundary.
2. Run `python -m pytest tests -q`.
3. Run `python -m compileall alphapilot`.
4. Run `python -m alphapilot.scripts.validate_config` and `scripts/check_safety.ps1`.
5. Run `git diff --check`.
6. Commit as `Document bounded strategy evolution`.

## Task 8: Runtime safety closeout

1. Do not run a full multi-million-row formal backtest inside the feature worktree; use deterministic fixture tests and existing report fixtures.
2. Do not mutate `D:\Codex-Workspace\回测数据` or the user's production registry during tests.
3. Do not create Demo/Live releases, orders, or approvals.
4. Report that existing immutable Demo releases keep their old exit rules; only a newly validated successor may adopt the trend runner.
