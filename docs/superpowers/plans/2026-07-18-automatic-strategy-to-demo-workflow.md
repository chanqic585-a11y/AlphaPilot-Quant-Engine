# V19-V24 Automatic Strategy-to-Demo Workflow Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** Implement a bounded, resumable, evidence-preserving workflow from data capability through exact-hash-gated OKX Demo admission without changing V18.3 results or safety boundaries.

**Architecture:** Add a candidate-neutral orchestration layer in the Quant repository, reuse the existing formal-validation and immutable-release cores, and add only the Console admission/audit extensions needed for V24. Every stage emits canonical artifacts and an append-only hash chain. Formal result execution remains one-shot and Console import remains unapproved/disarmed.

**Tech Stack:** Python 3.11+, dataclasses, JSON/SQLite, pytest, existing AlphaPilot hashing/checkpoint/formal-validation/release contracts, PowerShell verification scripts.

---

### Task 1: Freeze the design, prompt, and program schemas

**Files:**
- Create: `alphapilot/research_factory/program_types.py`
- Create: `alphapilot/research_factory/artifact_paths.py`
- Create: `tests/research_factory/test_automatic_program_types.py`
- Create: `docs/superpowers/specs/2026-07-18-automatic-strategy-to-demo-workflow-design.md`
- Create: `docs/superpowers/plans/2026-07-18-automatic-strategy-to-demo-workflow.md`

1. Write failing tests for canonical program IDs, immutable budgets, terminal routes, and dynamic artifact paths.
2. Implement frozen dataclasses and canonical serialization.
3. Verify no private credential, approval, ARM, order, or Live field exists in research state.
4. Run the targeted tests, then commit and push the pre-result architecture.

### Task 2: Implement V19 data capability and causal field semantics

**Files:**
- Create: `alphapilot/research_factory/data_capability.py`
- Create: `alphapilot/research_factory/data_profiles.py`
- Create: `alphapilot/research_factory/field_semantics.py`
- Create: `alphapilot/research_factory/available_at.py`
- Create: `tests/research_factory/test_data_capability.py`
- Create: `alphapilot/scripts/run_automatic_strategy_demo.py`

1. Write failing tests for `availableAt`, verified-source requirements, profile selection, missing-derivatives behavior, and fail-closed candidate data gates.
2. Implement the three versioned data profiles and deterministic capability matrix.
3. Add the CLI `init` and `run-stage --stage v19` commands.
4. Emit V19 capability, profile, field-semantics, checkpoint, and manifest artifacts.
5. Run targeted and full tests; commit, push, and tag V19.

### Task 3: Implement resumable orchestration and the append-only ledger

**Files:**
- Create: `alphapilot/research_factory/program_ledger.py`
- Create: `alphapilot/research_factory/program_state.py`
- Create: `alphapilot/research_factory/orchestrator.py`
- Create: `alphapilot/research_factory/resume.py`
- Create: `alphapilot/research_factory/stage_gates.py`
- Create: `tests/research_factory/test_program_resume.py`

1. Write failing tests for interruption, monotonic sequence, previous-record hashes, duplicate command idempotence, checkpoint corruption, and budget exhaustion.
2. Implement atomic state/checkpoint writes and an append-only canonical ledger.
3. Make stage reruns return the prior result without consuming formal-run budget.
4. Run tests and a simulated interruption/resume smoke test.

### Task 4: Implement V20 independent mechanism and candidate generation

**Files:**
- Create: `alphapilot/research_factory/automatic_hypotheses.py`
- Create: `alphapilot/research_factory/automatic_candidates.py`
- Create: `alphapilot/research_factory/directional_candidate_adapter.py`
- Create: `tests/research_factory/test_automatic_candidates.py`

1. Write failing tests for first-batch family/timeframe rules, maximum two variants, maximum eight families, semantic dedup, no performance fields, immutable ExitPolicy, and adapter identity.
2. Implement deterministic directional-event mechanism templates driven only by V19 capability.
3. Bind candidates through `CandidateAdapter` without adding candidate imports to the formal core.
4. Emit hypothesis/candidate registries and hashes; commit, push, and tag V20.

### Task 5: Implement V21 bounded prefilter and preregistration freeze

**Files:**
- Create: `alphapilot/research_factory/automatic_prefilter.py`
- Create: `alphapilot/research_factory/automatic_preregistration.py`
- Create: `tests/research_factory/test_automatic_prefilter.py`

1. Write failing tests for survivor limits, frozen comparison panels, Advisory-R handling, formal-candidate budget, and absence of formal-pass claims.
2. Reuse existing event-replay and screening metrics through a narrow adapter.
3. Freeze candidate IDs, hashes, data snapshot, costs, splits, gates, comparisons, and formal run budgets.
4. Require the preregistration commit to be committed and pushed before V22.
5. Commit, push, and tag V21.

### Task 6: Implement V22 one-shot formal execution and mechanical routing

**Files:**
- Create: `alphapilot/research_factory/formal_stage.py`
- Create: `tests/research_factory/test_formal_stage.py`
- Modify: `alphapilot/scripts/run_automatic_strategy_demo.py`

1. Write failing tests for remote-freeze authentication, explicit preregistration/candidate input, one formal run, independent result-read count, result classes, and no gate mutation.
2. Wrap the reusable generic formal command; do not import S01 in the workflow core.
3. Emit candidate-scoped artifacts and route failed candidates/campaigns mechanically.
4. Run no formal result until the implementation and preregistration commits are pushed.
5. Execute the bounded formal stage once, publish evidence, and commit/tag V22 closeout.

### Task 7: Implement V23 standard and research-forward immutable releases

**Files:**
- Create: `alphapilot/research_factory/release_stage.py`
- Create: `tests/research_factory/test_release_stage.py`
- Modify: `alphapilot/evolution/promotion/strategy_validation_release.py`

1. Write failing tests for evidence-class eligibility, maximum three releases, ranking, limitation preservation, hash-addressed bytes, and unapproved imports.
2. Extend the existing release builder with an explicit versioned V2 schema while retaining V1 compatibility.
3. Emit zero releases truthfully when no candidate qualifies.
4. Commit, push, and tag V23 before Console import.

### Task 8: Implement V24 Console import and exact-hash gate

**Files:**
- Create: `alphapilot_control_console/automatic_strategy_demo_admission.py`
- Create: `tests/test_automatic_strategy_demo_admission.py`
- Modify: `alphapilot_control_console/strategy_validation_release_service.py`
- Modify: `alphapilot_control_console/strategy_validation_release_store.py`

1. Write failing tests that import creates no approval, no ARM, no order, and no strategy statistic.
2. Add an admission report containing release hashes, approval state, Runtime state, Demo universe state, and engineering-smoke isolation.
3. Stop at `blocked_waiting_exact_release_approval` when releases exist and await explicit user approval of each exact hash.
4. If zero releases exist, verify the zero-release path and close as `completed_zero_qualified_candidates`.
5. After explicit approval only, verify separate ARM and first closed-candle scan; never enable Live or Withdraw.
6. Run Console targeted/full tests; commit, push, and tag V24 when its legal terminal route is reached.

### Task 9: Produce the final evidence bundle and repository closeout

**Files:**
- Create: `reports/automatic_strategy_demo/<programId>/program_summary.json`
- Create: `reports/automatic_strategy_demo/<programId>/program_summary.md`
- Create: `reports/automatic_strategy_demo/<programId>/artifact_manifest.json`
- Create: `reports/automatic_strategy_demo/<programId>/verification_report.json`

1. Verify every artifact hash and ledger link.
2. Run Quant and Console full tests, compile checks, config validation, safety scripts, and `git diff --check`.
3. Confirm no credential, Withdraw, Live enablement, automatic approval, or hidden gate relaxation exists.
4. Push all stage commits/tags and report exact repository status, terminal route, release hashes, and any required human action.

## Mandatory Stop Conditions

- Stop before approval when an exact release hash needs human authorization.
- Stop and report if publication/remote-freeze authentication fails.
- Stop and report if private credentials are required; never persist or print them.
- Close honestly with zero releases when all bounded campaigns fail.
- Never rerun a claimed formal candidate or edit a frozen preregistration/release.
