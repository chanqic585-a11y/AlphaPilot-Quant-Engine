# V25-V26 Capacity Data Semantics and Frozen Candidate Replay Plan

> **For Codex:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task with review checkpoints.

**Goal:** Correct the V19-V24 capacity-data classification, build a verified capacity-ready data contract, and replay the one frozen candidate exactly once only if all V25 readiness gates pass.

**Architecture:** Add candidate-neutral layered data contracts and fail-closed gates in the Quant research factory. Audit volume provenance independently from strategy performance, derive conservative turnover only through preregistered semantic routes, and preserve the original completed-zero result through a sidecar clarification. V26 consumes a new immutable data snapshot while keeping the candidate, capital policy, costs, split, gates, and exit policy unchanged.

**Safety boundary:** Research and immutable evidence only. No API credentials, private exchange calls, order placement, approval, ARM, Live, Trade API, or Withdraw capability. Missing semantics block before a formal claim and consume no formal-run budget.

---

### Task 1: Preserve the original result and freeze the repair design

**Files:**
- Create: `reports/automatic_strategy_demo/<programId>/v25/original_result_classification_sidecar.json`
- Create: `docs/superpowers/specs/2026-07-18-v25-v26-capacity-data-semantics-design.md`
- Create: `docs/superpowers/plans/2026-07-18-v25-v26-capacity-data-semantics-frozen-replay.md`

1. Hash the original V19-V24 artifacts and verify they are unchanged.
2. Classify the completed-zero result as a capacity-data semantic block, not a strategy-performance or implementation failure.
3. Record the frozen candidate and all fields that V26 is prohibited from changing.

### Task 2: Implement layered end-to-end data contracts

**Files:**
- Create: `alphapilot/research_factory/end_to_end_data_contract.py`
- Create: `alphapilot/research_factory/data_dependency_graph.py`
- Create: `alphapilot/research_factory/formal_data_gate.py`
- Create: `alphapilot/research_factory/demo_data_gate.py`
- Create: `tests/research_factory/test_end_to_end_data_contract.py`
- Create: `tests/research_factory/test_formal_data_gate.py`

1. Write failing tests for signal-ready, formal-ready, and demo-ready profiles.
2. Model signal, ranking, exit, capital, cost, benchmark, statistical, Demo, and optional-diagnostic dependencies.
3. Require semantic verification and minimum event coverage before a formal claim.
4. Return `formal_data_blocked_before_claim` without incrementing Claim, Attempt, Result, or Read counts when the gate fails.
5. Export `capital_policy_data_dependencies.json` with stable hashes.

### Task 3: Audit volume provenance and turnover semantics

**Files:**
- Create: `alphapilot/data_provenance/volume_provenance_audit.py`
- Create: `alphapilot/data_provenance/volume_semantics_verifier.py`
- Create: `alphapilot/data_provenance/turnover_derivation.py`
- Create: `tests/data_provenance/test_volume_provenance_audit.py`
- Create: `tests/data_provenance/test_turnover_derivation.py`

1. Write failing tests for exact quote turnover, conservative base-volume lower bounds, verified contract conversion, unavailable semantics, and exchange-identity mismatch.
2. Audit ADA, BCH, BTC, ETC, ETH, LINK, LTC, and XRP at 1h, 4h, and 1d.
3. Never label `close * volume` as exact turnover.
4. Require full contract metadata before contract-volume conversion.
5. Emit field-level lineage and availability evidence without reading strategy performance.

### Task 4: Freeze the capacity-ready profile and certify real signal usage

**Files:**
- Modify: `alphapilot/research_factory/data_profiles.py`
- Modify: `alphapilot/research_factory/data_capability.py`
- Create: `alphapilot/research_factory/capacity_profile_certification.py`
- Create: `tests/research_factory/test_capacity_profile_certification.py`

1. Create `ohlcv_verified_capacity_v2` only when all mandatory semantics are verified.
2. Filter unavailable instruments only by preregistered data readiness, never by PnL or strategy outcome.
3. Run the frozen signal path without PnL, exits, or statistical gates and require assigned, available, and calculated event counts to be positive.
4. Freeze the profile, snapshot, universe decision, lineage hashes, and certification report.

### Task 5: Execute the bounded V26 replay conditionally

**Files:**
- Create: `alphapilot/research_factory/program_v25.py`
- Create: `alphapilot/research_factory/program_v26.py`
- Create: `tests/research_factory/test_program_v25_v26.py`
- Modify: `alphapilot/scripts/run_automatic_strategy_demo.py`

1. If V25 is not formal-ready, stop truthfully with V26 not started and zero formal claims.
2. If V25 is formal-ready, create `automatic_strategy_demo_capacity_replay_<hash>` using only the frozen candidate `auto-trend_failure_reversal-4h-short-v2`.
3. Re-run the preregistered prefilter and publish a new immutable preregistration before any formal result is read.
4. Execute exactly one formal Claim, Attempt, Result, and Read; keep Locked OOS reads at zero.
5. Route mechanically and create no release unless the unchanged formal gate passes.

### Task 6: Validate, publish evidence, and close out

1. Run targeted tests first, then `pytest tests -q --import-mode=importlib`.
2. Run `python -m compileall alphapilot` and repository safety checks.
3. Verify original V19-V24 artifacts have zero byte changes.
4. Commit and push Quant, Console if touched, and Docs.
5. Tag only completed versions. Do not create a V26 tag if V26 is correctly blocked before execution.
6. Report data readiness, lineage routes, formal ledger counts, release count, Demo state, Git hashes, tags, clean status, and known limitations.
