# Formal Backtest Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove repeated full-frame pandas work from every formal trade evaluation while preserving byte-for-byte-equivalent result values.

**Architecture:** Prepare sorted numeric execution and funding arrays once per instrument. Evaluate signal windows with binary search and reuse the prepared object for baseline and stress. Prepare regime timestamps once and use binary search for lookup.

**Tech Stack:** Python 3, pandas, numpy, unittest, SQLite-backed evolution workflow.

## Global Constraints

- No strategy, risk, cost, split, or safety-boundary changes.
- No new dependency.
- Result parity is required before performance claims.
- Only one paused workflow may be resumed for operational verification.

---

### Task 1: Prepared fixed-R execution path

**Files:**
- Modify: `alphapilot/evolution/evaluation/fixed_r_path.py`
- Modify: `tests/evolution/test_fixed_r_path.py`

**Interfaces:**
- Produces: `prepare_fixed_r_execution_path(...) -> PreparedFixedRExecutionPath`
- Produces: `evaluate_prepared_fixed_r_path(...) -> FixedRPathResult`

- [ ] Add a failing deterministic parity test covering all result fields for repeated signals.
- [ ] Run `python -m unittest tests.evolution.test_fixed_r_path -v` and confirm the new API is missing.
- [ ] Implement immutable prepared arrays, binary entry lookup, funding prefix/range lookup, and the compatibility wrapper.
- [ ] Run the focused test and existing fixed-R tests to green.

### Task 2: Formal runner integration and regime lookup

**Files:**
- Modify: `alphapilot/evolution/evaluation/formal_strategy_backtest.py`
- Modify: `tests/evolution/test_formal_strategy_backtest.py`

**Interfaces:**
- Consumes: prepared fixed-R path APIs from Task 1.
- Produces: one prepared execution object per instrument and O(log n) regime lookup.

- [ ] Add failing tests proving preparation is reused for baseline/stress and regime lookup preserves boundary behavior.
- [ ] Run the focused formal-backtest tests and confirm the new reuse assertions fail.
- [ ] Add lazy per-instrument preparation cache and prepared regime timestamps/labels.
- [ ] Run focused tests to green.

### Task 3: Performance and regression verification

**Files:**
- Create: `scripts/benchmark_formal_fixed_r_path.py`
- Modify: `README.md`

**Interfaces:**
- Produces: deterministic JSON benchmark summary with parity, elapsed time, and speedup ratio.

- [ ] Add a benchmark command that compares repeated compatibility preparation with one prepared path on deterministic synthetic data.
- [ ] Run it and require exact parity plus a material speedup.
- [ ] Run all evolution tests, `python -m compileall alphapilot`, config validation, safety scan, and `git diff --check`.
- [ ] Commit the verified Quant change before operational resume.

### Task 4: One-run operational verification

**Files:**
- No production-code changes unless a new failing test reproduces a discovered defect.

**Interfaces:**
- Consumes: one existing paused workflow run.
- Produces: measured elapsed time, result path, status, and comparison with the previous 8h50 incomplete run.

- [ ] Back up `evolution_registry.sqlite` online.
- [ ] Resume only the 15m paused run.
- [ ] Monitor CPU, workflow phase, result creation, and elapsed time without starting the remaining queue.
- [ ] Stop and diagnose if parity, memory, or progress evidence is missing.
