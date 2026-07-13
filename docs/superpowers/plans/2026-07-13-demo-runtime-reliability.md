# Demo Runtime Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist and recover the OKX public Demo runtime trigger path without bypassing confirmed-close, immutable Release, or risk gates.

**Architecture:** Add a bounded audit sink for public runtime lifecycle and close events. The unified runner observes runtime health, attempts bounded public-only recovery when Demo is desired, and links each confirmed-close event to exactly one evaluation result. Workflow projection reports evaluated count separately from match count.

**Tech Stack:** Python 3, SQLite, unittest, OKX public WebSocket runtime, local Flask console.

## Global Constraints

- WebSocket confirmed close remains required for evaluation.
- Recovery may reconnect public data only and cannot create orders itself.
- No raw credential persistence, Withdraw, immutable Release mutation, risk bypass, or Live enablement.

---

### Task 1: Runtime audit store

**Files:**
- Create: `alphapilot_control_console/demo_runtime_audit_store.py`
- Create: `tests/test_demo_runtime_audit_store.py`

**Interfaces:**
- Produces: `DemoRuntimeAuditStore.record(event_type, payload)` and bounded `recent(limit)`.

- [ ] Add failing tests for schema creation, bounded JSON records, and credential-key redaction.
- [ ] Run focused tests and confirm the module is missing.
- [ ] Implement append-only audit records in the existing unified SQLite database.
- [ ] Run focused tests to green.

### Task 2: Public runtime lifecycle observations

**Files:**
- Modify: `alphapilot_control_console/okx_public_market_runtime.py`
- Modify: `alphapilot_control_console/demo_market_runtime_registry.py`
- Modify: `tests/test_okx_public_market_runtime.py`
- Modify: `tests/test_demo_market_runtime_registry.py`

**Interfaces:**
- Consumes: audit callback supplied by registry.
- Produces: startup, connection, recovery, and confirmed-close observations.

- [ ] Add failing tests for disconnect/reconnect and confirmed-close observations.
- [ ] Run focused tests and verify expected failures.
- [ ] Add state-transition observations with no credentials or unbounded payloads.
- [ ] Run focused tests to green.

### Task 3: Runner watchdog and evaluation chain

**Files:**
- Modify: `alphapilot_control_console/unified_auto_execution_runner.py`
- Modify: `alphapilot_control_console/unified_auto_execution_controller.py`
- Modify: `tests/test_unified_auto_execution_runner.py`
- Modify: `tests/test_unified_auto_execution_controller.py`

**Interfaces:**
- Consumes: runtime status and bounded recovery callback.
- Produces: not-evaluated blocker, close received, evaluation started, and evaluation completed audit events.

- [ ] Add failing tests that a cold desired Demo runtime triggers recovery but never evaluation without a close event.
- [ ] Add failing tests that one close sequence yields one completed evaluation chain.
- [ ] Implement bounded watchdog and linked audit records.
- [ ] Run focused tests to green.

### Task 4: Projection and full verification

**Files:**
- Modify: `alphapilot_control_console/demo_workflow_projection.py`
- Modify: `tests/test_demo_workflow_projection.py`
- Modify: `README.md`

**Interfaces:**
- Produces: explicit evaluated-release, matched-signal, order, blocker, and last-close status.

- [ ] Add failing projection tests for zero evaluated versus evaluated-zero-match.
- [ ] Implement concise Chinese status text and audit summary.
- [ ] Run all Console tests, compileall, safety scan, and `git diff --check`.
- [ ] Commit before any credentialed operational restart.

### Task 5: Public-only soak and gated Demo verification

**Files:**
- No production-code changes unless a new failing test reproduces a discovered defect.

**Interfaces:**
- Produces: confirmed public runtime health and close-event audit evidence.

- [ ] Back up unified and Demo execution SQLite databases online.
- [ ] Start public runtime without placing orders and observe one real close event.
- [ ] Verify the audit store records connection, close receipt, and evaluation state accurately.
- [ ] Request process-only Demo credentials only if credentialed ARM is necessary after public validation.
