# V13.27.4 Workflow Pause, Queue, and Demo Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver truthful pause/resume, visible serial batch queueing, automatic local-forward startup, and an audited local-forward-to-Demo release control.

**Architecture:** Quant Engine owns durable worker interruption, lock handoff, serial queue order, and immutable candidate identity. Control Console owns safe recovery orchestration and the user-facing audited Demo override. Existing Demo and Live runtime isolation remains unchanged.

**Tech Stack:** Python 3, SQLite append-only workflow registry, Windows process-safe file locks, vanilla JavaScript UI, unittest.

## Global Constraints

- Historical point-in-time dynamic Top50 remains the formal backtest universe.
- Target reward/risk remains at least 2R.
- Public data only during backtest and local forward.
- An override may enter OKX Demo but cannot directly enable Live execution.
- No Withdraw endpoint or raw credential persistence.
- One heavy backtest worker at a time.

---

### Task 1: Make official-data collection interruptible

**Files:**
- Modify: `alphapilot/data_foundation/okx_public.py`
- Modify: `alphapilot/data_foundation/official_history.py`
- Modify: `alphapilot/evolution/workflow/dual_layer.py`
- Test: `tests/data_foundation/test_okx_public.py`
- Test: `tests/data_foundation/test_official_history.py`

**Interfaces:**
- `history_candles(..., stop_requested: Callable[[], bool] | None = None)` raises a dedicated stop exception before the next page.
- `OkxOfficialHistoryCollector(..., stop_requested=...)` returns `status="paused"` without persisting a partial partition.

- [ ] Write failing pagination and collector interruption tests.
- [ ] Run the targeted tests and verify the missing stop behavior fails.
- [ ] Add the stop callback and dedicated interruption handling.
- [ ] Run targeted tests and commit the passing change.

### Task 2: Make resume wait for lock handoff

**Files:**
- Modify: `alphapilot/evolution/workflow/worker_lock.py`
- Modify: `alphapilot/evolution/workflow/cli.py`
- Test: `tests/evolution/test_workflow_worker_lock.py`
- Test: `tests/evolution/test_workflow_cli.py`

**Interfaces:**
- `workflow_worker_lock(..., wait_seconds=0.0, poll_seconds=0.1)` retains current nonblocking defaults.
- Resumed `one-click-backtest` waits for the paused worker lock before transitioning back to queued/running.

- [ ] Write a failing lock handoff test with a delayed release.
- [ ] Verify RED, implement bounded polling, and verify GREEN.
- [ ] Add a CLI resume regression test and commit.

### Task 3: Queue all selected runs before serial execution

**Files:**
- Modify: `alphapilot/evolution/workflow/cli.py`
- Test: `tests/evolution/test_workflow_cli.py`

**Interfaces:**
- `_run_selected_backtests` validates all IDs, queues all IDs, then calls one run at a time in request order.

- [ ] Write a failing test asserting the second run is already queued when the first worker begins.
- [ ] Verify RED, implement queue-first behavior, verify serial order, and commit.

### Task 4: Preserve local-forward candidate identity

**Files:**
- Modify: `alphapilot/evolution/workflow/local_forward_bridge.py`
- Test: `tests/evolution/test_workflow_local_forward_bridge.py`

**Interfaces:**
- Local-forward `result` and evidence contain `strategyCandidateId` from the immutable ForwardRelease lineage.

- [ ] Write the failing identity test.
- [ ] Add identity to initial, success, and failure result paths.
- [ ] Run targeted tests and commit.

### Task 5: Recover backtests as one serial batch

**Files:**
- Modify: `alphapilot_control_console/workflow_client.py`
- Test: `tests/test_workflow_startup_recovery.py`

**Interfaces:**
- `resume_incomplete_workflow_runs` calls `spawn_workflow_batch` once for eligible backtest IDs in deterministic order.

- [ ] Write a failing recovery serialization test.
- [ ] Implement grouped recovery and verify existing error reporting.
- [ ] Run targeted tests and commit.

### Task 6: Add local-forward audited Demo release control

**Files:**
- Modify: `alphapilot_control_console/demo_override_release.py`
- Modify: `alphapilot_control_console/demo_workflow_service.py`
- Modify: `web/app.js`
- Modify: `web/index.html`
- Modify: `web/styles.css`
- Test: `tests/test_demo_override_release.py`
- Test: `tests/test_workflow_ui_contract.py`

**Interfaces:**
- Local-forward cards open the existing confirmation dialog using `strategyCandidateId`.
- Override contract records missing evidence and `postDemoPromotionPolicy`, remains `livePromotionAllowed=false` before Demo completion, and creates no order.

- [ ] Write failing contract and UI tests.
- [ ] Add the local-forward action and explanatory copy.
- [ ] Verify targeted tests and commit.

### Task 7: Verify, merge, and safely restart the queue

**Files:**
- Modify: `README.md` in both repositories.
- Runtime state: `data/evolution_registry.sqlite` and existing checkpoints only after backup.

**Interfaces:**
- Production launch order is the 10 V13.27.3 short-cycle candidates first and Alpha191 last.

- [ ] Run full Quant and Console suites, compile checks, Node syntax, diff check, and safety scan.
- [ ] Back up the registry and verify no workflow worker is active.
- [ ] Merge and push both repositories without adding runtime directories.
- [ ] Start one serial selected-backtest worker and verify every selected run is queued while only one worker is active.
