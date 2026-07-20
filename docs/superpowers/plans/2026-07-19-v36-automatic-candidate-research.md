# V36 Automatic Candidate Research Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a bounded, deterministic V36 research route over the V35 registry without reading Locked OOS early or crossing into Demo/Live execution.

**Architecture:** Add a focused `automatic_candidate_research` package whose executor conforms to the existing V35 background-service protocol. Reuse V35 registry identities and existing Formal outcome semantics while keeping parameter selection, type projections, Formal routing, and artifact persistence independently testable.

**Tech Stack:** Python 3.12, dataclasses, canonical JSON/SHA-256, existing AlphaPilot stable hashing, unittest/pytest.

## Global Constraints

- Work only in `D:\Codex-Workspace\AlphaPilot-Quant-V36-worktree`.
- Preserve V35 source registry and historical artifacts.
- Preregister 3-8 finite trials per eligible family candidate.
- Development-only selection; zero Locked OOS reads before Formal routing.
- Reuse Formal/data/provenance contracts; do not duplicate statistical engines.
- Never use exchange credentials, private APIs, Demo/Live ARM, approval, or orders.
- Do not force a passing candidate.
- Do not commit or push.

---

### Task 1: Frozen Trial And Panel Contracts

**Files:**
- Create: `alphapilot/automatic_candidate_research/contracts.py`
- Create: `alphapilot/automatic_candidate_research/preregistration.py`
- Test: `tests/automatic_candidate_research/test_preregistration.py`

**Interfaces:**
- Produces: `build_preregistration(registry, campaign_id, created_at) -> dict[str, Any]`

- [x] Write tests that require 3 deterministic trials per eligible candidate, preserve blocked families, and freeze comparison-panel identity.
- [x] Run the tests and verify they fail because the V36 package is missing.
- [x] Implement the smallest immutable contracts and preregistration builder.
- [x] Run the tests and verify they pass (`2 passed`).

### Task 2: Type Projections And Stable Neighborhood

**Files:**
- Create: `alphapilot/automatic_candidate_research/selection.py`
- Test: `tests/automatic_candidate_research/test_selection.py`

**Interfaces:**
- Produces: `project_development_evidence(strategy_type, evidence)` and `select_stable_neighborhood(trials, projections)`.

- [x] Write tests for directional, pair, portfolio, and event fields plus Locked-OOS rejection.
- [x] Verify RED (`selection` module missing).
- [x] Implement canonical projections and the majority/non-spike/drawdown neighborhood gate.
- [x] Verify GREEN, including an isolated-best-point rejection (`7 passed`).

### Task 3: Formal Outcome Routing And Release Boundary

**Files:**
- Create: `alphapilot/automatic_candidate_research/formal_routing.py`
- Test: `tests/automatic_candidate_research/test_formal_routing.py`

**Interfaces:**
- Produces: `route_formal_outcomes(preregistration, selections, formal_records)`.

- [x] Write tests for the approved taxonomy, panel drift, zero winners, data-blocked outcomes, preregistered trial identity, and immutable release safety fields.
- [x] Verify RED (`formal_routing` module missing, then forged trial initially accepted).
- [x] Implement minimal deterministic routing without performing Formal calculations.
- [x] Verify GREEN (`4 passed`).

### Task 4: Executor, Artifacts, And CLI

**Files:**
- Create: `alphapilot/automatic_candidate_research/executor.py`
- Create: `alphapilot/automatic_candidate_research/__init__.py`
- Create: `alphapilot/scripts/run_v36_candidate_research.py`
- Test: `tests/automatic_candidate_research/test_executor.py`

**Interfaces:**
- Produces: `AutomaticCandidateResearchExecutor.execute(job)` compatible with V35 `ResearchService`.

- [x] Write end-to-end tests for deterministic artifacts, manifest hashes, V35 service integration, zero side effects, and valid zero-winner completion.
- [x] Verify RED (`executor` and CLI modules missing).
- [x] Implement atomic artifact persistence and one-shot CLI wiring.
- [x] Verify GREEN (`2 executor tests`, `1 CLI test`).

### Task 5: Verification And Bounded Smoke

**Files:**
- Modify: `docs/superpowers/plans/2026-07-19-v36-automatic-candidate-research.md`

- [x] Run all V36 and V35/research-service targeted tests.
- [x] Run compileall and relevant safety scans.
- [x] Run a no-credential bounded smoke and capture exact counts.
- [x] Run `git diff --check`, source whitespace checks, and leave all changes uncommitted for parent review.
