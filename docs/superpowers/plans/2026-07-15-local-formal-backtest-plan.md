# Local Formal Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace automatic OKX history downloads with immutable formal snapshots built only from the existing local data warehouse.

**Architecture:** Add a local formal-data collector that satisfies the existing collection interface without network access. Keep phase IDs and downstream backtest gates stable, while recording an explicit user-approved local provenance and updating projections/UI labels.

**Tech Stack:** Python 3.12, pandas, Parquet, SQLite workflow registry, unittest/pytest.

## Global Constraints

- Historical data source is `D:\Codex-Workspace\回测数据` only.
- No automatic historical download or exchange history request.
- Missing data blocks with an explicit gap report.
- Existing formal backtest gates, target R, walk-forward and cost stress remain unchanged.
- No API key, private exchange API, order, Withdraw or live-trading change.

---

### Task 1: Offline local formal collection

**Files:**
- Create: `alphapilot/data_foundation/local_formal_history.py`
- Modify: `alphapilot/data_foundation/formal_snapshot.py`
- Test: `tests/data_foundation/test_local_formal_history.py`
- Test: `tests/data_foundation/test_formal_snapshot.py`

**Interfaces:**
- Produces: `LocalFormalHistoryCollector.collect(contract) -> OfficialCollectionResult`
- Consumes: existing `StrategyDataContractRecord`, `WarehouseLayout`, catalog and canonical writers.

- [x] Write a failing test proving local files create a completed collection without a network client.
- [x] Write a failing test proving missing local coverage returns a blocked collection and performs no download.
- [x] Implement local universe selection, canonical reuse/conversion and local funding conversion.
- [x] Accept `user_approved_local` partitions in formal snapshot validation and record their provenance.
- [x] Run focused tests and confirm they pass.

### Task 2: Default workflow and user-visible state

**Files:**
- Modify: `alphapilot/evolution/workflow/dual_layer.py`
- Modify: `alphapilot/evolution/workflow/projection.py`
- Modify: `tests/evolution/test_dual_layer_workflow.py`
- Modify: `tests/evolution/test_workflow_backtest.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `LocalFormalHistoryCollector` from Task 1.
- Produces: default dual-layer workflow that cannot initiate an OKX history download.

- [x] Write a failing test proving default dependencies use local formal collection.
- [x] Write a failing projection test for local formal labels and evidence.
- [x] Wire the local collector into the default workflow while retaining legacy phase IDs.
- [x] Update blocker text, projection labels and documentation.
- [x] Run `python -m pytest tests -q`, `python -m compileall alphapilot`, safety scan and `git diff --check`.

### Task 3: Existing workflow migration and console copy

**Files:**
- Modify: persisted workflow runs in `data/evolution_registry.sqlite` through repository APIs.
- Modify in Console repo: `web/index.html`, `web/app.js`, related UI contract tests.

**Interfaces:**
- Consumes: paused/queued active backtest runs.
- Produces: resumable local-formal runs and UI that no longer promises official downloads.

- [x] Back up the workflow registry online before migration.
- [x] Clear only obsolete official-collection phase artifacts/checkpoints from active runs; preserve attempts, versions and local research artifacts.
- [x] Resume the selected run and keep the remaining active runs queued.
- [x] Update Console copy and run Console tests.
- [x] Verify no download worker or exchange history request is active.
