# AlphaPilot Advisory-R Workflow V13.27.1.14-V13.27.1.18 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace fixed 2R as a research and Demo-admission hard gate with immutable, preregistered Advisory-R exit policies, then run a bounded strategy funnel through prefilter, statistical audit, locked OOS, and evidence-only Demo release generation.

**Architecture:** Add a versioned `alphapilot.exit_policy` domain package that canonicalizes, validates, hashes, and causally executes four bounded exit modes while retaining legacy fixed-target behavior. Integrate that package into the existing research-screening contracts without rewriting historical artifacts, then build each campaign stage as a frozen-input report generator. Extend only the active Console strategy-validation/Demo path for schema-v2 imports and evidence display; leave Live admission unchanged.

**Tech Stack:** Python 3, dataclasses, pandas/numpy, scipy/statsmodels where already available, SQLite-backed Console services, vanilla JavaScript UI, PowerShell validation scripts, pytest/unittest.

## Global Constraints

- R remains the common risk-accounting unit; `minimumTargetR` is `null` for new Advisory-R research.
- Supported exit modes are exactly `fixed_r`, `partial_then_trailing`, `structure_or_time`, and `hybrid`.
- The initial stop can tighten but can never widen.
- Entry executes at next-bar open; same-bar stop/exit ambiguity is stop-first.
- Trailing updates use completed-bar data and become effective on the next bar.
- Structure/time decisions execute at the next bar open.
- Exit-policy parameters, canonical JSON, and hash are frozen before result access.
- Historical campaign/release bytes and hashes remain unchanged.
- Economic, cost, drawdown, sample, walk-forward, statistical, OOS, and concentration gates remain hard gates.
- Exit variants count as trials; no result-after mode or parameter switching.
- V15 has at most 8 families and 12 candidates; V16 at most 6; V17 at most 3; V18 at most 3 releases.
- Zero survivors are a valid result and stop the next stage.
- No API-key persistence, Trade API, Withdraw API, Demo order, Live order, automatic ARM, or Live-admission change.

---

### Task 1: Freeze V13.27.1.14 migration inventory and policy contract

**Files:**
- Create: `alphapilot/exit_policy/__init__.py`
- Create: `alphapilot/exit_policy/models.py`
- Create: `alphapilot/exit_policy/schema.py`
- Create: `alphapilot/exit_policy/canonical.py`
- Create: `alphapilot/exit_policy/validation.py`
- Create: `tests/exit_policy/test_models_and_validation.py`
- Create: `alphapilot/reports/generate_exit_policy_migration_inventory.py`
- Create: `tests/reports/test_exit_policy_migration_inventory.py`
- Create: `reports/exit_policy/migration_inventory.json`
- Create: `reports/exit_policy/migration_summary.md`

**Interfaces:**
- Produces: `ExitPolicy`, `ExitPolicyMode`, `canonical_exit_policy(policy)`, `exit_policy_hash(policy)`, `validate_exit_policy(policy)`.
- Produces: migration rows with `path`, `line`, `classification`, `active`, `action`, and `reason`.

- [ ] Write failing tests for valid sub-2R fixed exits, null-target structure exits, bounded partial/trailing parameters, structure-rule whitelist, positive maximum hold, and unbounded/unknown-field rejection.
- [ ] Run `python -m pytest tests/exit_policy/test_models_and_validation.py -q --import-mode=importlib` and confirm failures are caused by missing package APIs.
- [ ] Implement frozen policy dataclasses and strict canonical validation. Permit only declarative structure predicates from a versioned whitelist; reject arbitrary callbacks or expressions.
- [ ] Re-run the policy tests and confirm pass.
- [ ] Write failing migration-inventory tests that distinguish active research/Demo gates from historical reports, retired UI, tests, and negative safety wording.
- [ ] Implement deterministic inventory generation without editing historical artifacts, generate the two migration reports, and verify the active hit count is explicit.
- [ ] Commit Quant changes with `Implement Advisory-R exit policy contracts`.

### Task 2: Implement causal leg-level exit execution

**Files:**
- Create: `alphapilot/exit_policy/exit_legs.py`
- Create: `alphapilot/exit_policy/engine.py`
- Create: `alphapilot/exit_policy/reporting.py`
- Create: `tests/exit_policy/test_engine.py`
- Create: `tests/exit_policy/test_legacy_parity.py`
- Modify: `alphapilot/research_screening/exit_geometry.py`

**Interfaces:**
- Consumes: `ExitPolicy` and frozen entry/stop/candle/cost inputs.
- Produces: `ExitExecutionResult` with ordered legs, weighted gross/net R, fee/slippage/spread/funding R, MFE, MAE, giveback, and immutable policy identity.
- Produces: `replay_exit_policy(...) -> ExitExecutionResult`.

- [ ] Write failing tests for next-bar entry, stop-first ambiguity, fixed target below 2R, weighted partial costs, trailing tightening only, next-bar trailing activation, structure/time next-open execution, conservative gap fills, MFE/MAE, and total leg fractions equal to one.
- [ ] Run the engine tests and confirm expected failures.
- [ ] Implement the minimal causal engine and immutable leg/result models.
- [ ] Re-run engine tests and confirm pass.
- [ ] Write a golden legacy parity test using existing fixed-2R events and candidate hashes.
- [ ] Add a legacy adapter that interprets target-only candidates in memory as `fixed_r` without changing serialized legacy bytes, then confirm golden parity.
- [ ] Commit Quant changes with `Add causal Advisory-R exit execution`.

### Task 3: Integrate Advisory-R into research contracts and reports

**Files:**
- Create: `alphapilot/exit_policy/legacy_adapter.py`
- Modify: `alphapilot/research_screening/campaign_contract.py`
- Modify: `alphapilot/research_screening/campaign_signals.py`
- Modify: `alphapilot/research_screening/campaign_runner.py`
- Modify: `alphapilot/research_screening/campaign_preregistration.py`
- Modify: `tests/research_screening/test_campaign_contract.py`
- Modify: `tests/research_screening/test_campaign_signals.py`
- Modify: `tests/research_screening/test_campaign_runner.py`
- Create: `reports/exit_policy/exit_policy_bounds.json`
- Create: `reports/exit_policy/exit_policy_schema.json`

**Interfaces:**
- `CandidateSpec.targetR` becomes optional for schema-v2 candidates and `exitPolicy` is required for schema v2.
- `CandidateSpec.to_dict()` includes `exitPolicyVersion`, canonical policy, and `exitPolicyHash` in the definition hash.
- `build_campaign_preregistration()` emits `targetRGateMode=advisory`, `minimumTargetR=null`, and `exitPolicyRequired=true` only for the new schema.

- [ ] Add failing contract tests for schema-v2 policies and unchanged schema-v1 behavior.
- [ ] Add failing replay tests proving the runner uses the new engine and emits leg-level attribution.
- [ ] Implement dual-schema contracts, runner integration, and report fields without mutating old preregistrations or reports.
- [ ] Run all exit-policy and research-screening targeted tests.
- [ ] Generate and hash the bounds/schema artifacts.
- [ ] Commit Quant changes with `Integrate Advisory-R into research campaigns`.

### Task 4: Add Console schema-v2 import and Demo admission compatibility

**Files:**
- Modify: `alphapilot_control_console/strategy_validation_release_store.py`
- Modify: `alphapilot_control_console/demo_evidence.py`
- Modify: `alphapilot_control_console/demo_workflow_service.py`
- Modify: `alphapilot_control_console/demo_release_scanner.py`
- Modify: `tests/test_strategy_validation_release_store.py`
- Modify: `tests/test_demo_evidence.py`
- Modify: `tests/test_demo_workflow_actions.py`
- Modify: `tests/test_live_release_service.py`

**Interfaces:**
- Importer accepts legacy schema-v1 bytes unchanged and validates schema-v2 canonical exit policy/hash.
- Demo readiness requires a complete immutable exit policy instead of `targetR >= 2` for schema v2.
- Live service continues to enforce its existing admission boundary.

- [ ] Write failing tests for v2 fixed-R below 2, v2 null target with structure/time exit, incomplete policy rejection, mutable stop rejection, policy-hash mismatch rejection, default unapproved status, approval without ARM, and unchanged Live behavior.
- [ ] Run targeted Console tests and confirm expected failures.
- [ ] Implement dual-schema import/admission and remove only active Demo fixed-2R blockers.
- [ ] Re-run targeted tests and ensure legacy import bytes remain identical.
- [ ] Commit Console changes with `Support Advisory-R Demo releases`.

### Task 5: Finish V13.27.1.14 evidence, docs, and hard gate

**Files:**
- Modify: `README.md` in Quant and Console as needed.
- Create: `AlphaPilot-Docs/prompts/AlphaPilot_V13.27.1.14_Advisory_R_Exit_Policy_Implementation.md`
- Modify: `AlphaPilot-Docs/README.md`

**Interfaces:**
- Produces a V14 acceptance record with migration counts, mode tests, legacy parity hash, Console import results, Live unchanged, and zero campaign/holdout/release/ARM/order counts.

- [ ] Copy the authoritative V14 prompt into Docs and add concise architecture/navigation notes.
- [ ] Run Quant targeted and full tests, compile, config validation, safety scan, and diff check.
- [ ] Run Console full unittest, compile, Node syntax check, HTTP smoke, safety assertions, and diff check.
- [ ] Verify no campaign, holdout access, release, approval, ARM, or order was created.
- [ ] Commit/push/tag Quant `v13.27.1.14`, Console `v13.27.1.14-console`, and Docs `v13.27.1.14-docs` only after all checks pass.

### Task 6: Build and freeze V13.27.1.15 candidate inventory

**Files:**
- Create: `alphapilot/advisory_r_campaign/__init__.py`
- Create: `alphapilot/advisory_r_campaign/candidates.py`
- Create: `alphapilot/advisory_r_campaign/trial_ledger.py`
- Create: `alphapilot/advisory_r_campaign/preregistration.py`
- Create: `tests/advisory_r_campaign/test_candidates.py`
- Create: `tests/advisory_r_campaign/test_preregistration.py`
- Create: `research/preregistrations/<campaignId>_prefilter_v2.json`

**Interfaces:**
- Produces 8-12 candidates across 6-8 independent families, at most two variants per family, each with exactly one primary exit policy and stable semantic/definition/policy hashes.
- Produces `TrialLedger` rows that count every viewed exit-policy variant as a trial.

- [ ] Write failing inventory tests for candidate/family budgets, required hypothesis/falsification fields, mechanism-matched primary policy, diagnostic-only flag, trial identity, no post-result fields, and advisory-R preregistration fields.
- [ ] Implement deterministic candidates S01-S10 with declarative feature/entry/stop/exit definitions and one primary policy each.
- [ ] Freeze the preregistration and commit/push before reading any result.

### Task 7: Run V13.27.1.15 representative-universe prefilter

**Files:**
- Create: `alphapilot/advisory_r_campaign/signals.py`
- Create: `alphapilot/advisory_r_campaign/prefilter.py`
- Create: `alphapilot/advisory_r_campaign/reporting.py`
- Create: `tests/advisory_r_campaign/test_signals.py`
- Create: `tests/advisory_r_campaign/test_prefilter.py`
- Generate under `reports/advisory_r_campaign/<campaignId>/prefilter/`: `strategy_inventory.json`, `novelty_audit.json`, `trial_ledger.json`, `trial_ledger.csv`, `representative_universe.json`, `prefilter_results.json`, `exit_policy_attribution.json`, `simple_benchmarks.json`, `prefilter_gate_matrix.json`, `archived_prefilter_failures.json`, `prefilter_summary.md`.

**Interfaces:**
- Produces economic prefilter metrics from realized leg-level net R and a deterministic one-survivor-per-family router capped at six.

- [ ] Write failing causal signal tests for each registered mechanism and missing-data rejection.
- [ ] Implement only preregistered features/signals using existing local governed snapshots; do not download new broad data or access holdout.
- [ ] Write failing gate/router tests for event and portfolio thresholds, stable tie-break order, one candidate per family, and no target-R gate.
- [ ] Implement prefilter, diagnostics, and atomic report generation.
- [ ] Run the prefilter once, freeze outputs, verify `Holdout=0`, `Release=0`, `ARM=false`, `Order=0`.
- [ ] If survivor count is zero, commit/push/tag V15 evidence and stop V16-V18 as required. Otherwise route at most six survivors.

### Task 8: Run V13.27.1.16 walk-forward and statistical audit if eligible

**Files:**
- Create: `alphapilot/advisory_r_campaign/walk_forward.py`
- Create: `alphapilot/advisory_r_campaign/statistical_audit.py`
- Create: `tests/advisory_r_campaign/test_walk_forward.py`
- Create: `tests/advisory_r_campaign/test_statistical_audit.py`
- Generate: frozen V16 matrix, clustering, Newey-West, BH/BY, DSR, PBO, SPA/White-RC, capital-competition, and exit-attribution reports.

**Interfaces:**
- Consumes only frozen V15 survivor hashes and preregistration.
- Produces at most three Basic Pass candidates, one per family and return-correlation cluster.

- [ ] Write failing tests for hash mismatch fail-closed, five purged/embargoed folds, capital/risk competition including every exit leg, daily return matrix null-vs-zero semantics, clustering, actual-trial DSR, deterministic bootstrap seed, and gate thresholds.
- [ ] Implement and run the audit without adding candidates or changing exit policies.
- [ ] Verify locked OOS access remains zero.
- [ ] If Basic Pass is zero, commit/push/tag V16 evidence and stop V17; otherwise freeze at most three candidates.

### Task 9: Run V13.27.1.17 one-time locked OOS if eligible

**Files:**
- Create: `alphapilot/advisory_r_campaign/locked_oos.py`
- Create: `tests/advisory_r_campaign/test_locked_oos.py`
- Generate: `locked_oos_results.json`, `exit_policy_oos_attribution.json`, `translation_parity.json`, `formal_gate_matrix.json`, `failure_attribution.json`, `campaign_summary.md`, and optional `formal_pass_evidence/*.json`.

**Interfaces:**
- Consumes a fully frozen hash envelope and increments holdout access exactly once.
- Produces zero to three immutable formal evidence files.

- [ ] Write failing tests for access count one, any post-unlock hash/parameter change fail-closed, leg-level translation identity, numerical tolerance scope, and formal gates.
- [ ] Commit/push the frozen pre-unlock identity before opening OOS.
- [ ] Run OOS once, write reports atomically, and permanently close the campaign on failure.
- [ ] Verify `Release=0`, `ARM=false`, `Order=0`, then commit/push/tag V17.

### Task 10: Implement V13.27.1.18 release generation, approval boundary, and UI

**Files:**
- Modify: `alphapilot/scripts/generate_strategy_validation_releases.py`
- Modify/Create tests under `tests/evolution/` for release schema v2.
- Modify Console release/import/approval tests and services from Tasks 4-5.
- Modify: `web/app.js`
- Modify: `web/index.html` and `web/styles.css` only if existing evidence containers require it.
- Create: Docs V18 prompt and closeout report.

**Interfaces:**
- Generates a schema-v2 release only from V17 formal evidence, with complete frozen hash chain, `environment=demo`, `approvalRequired=true`, `approved=false`, and `liveEligible=false`.
- UI displays stage, evidence type, family, policy mode, advisory target R, realized net R, statistical/OOS state, and Release/Approval/ARM separately.

- [ ] Write failing Quant tests for 0-release and formal-pass release generation.
- [ ] Write failing Console tests for v1/v2 import, incomplete/mutable/hash-changed policy rejection, default unapproved, approval without ARM, and Live unchanged.
- [ ] Write failing UI contract tests for Advisory-R wording and prohibition of profitability claims.
- [ ] Implement release generation, Console validation, and concise evidence UI.
- [ ] Run Quant and Console full validation suites.
- [ ] Verify generated releases are zero when no formal pass; otherwise at most three, all unapproved; `ARM=false`, `Orders=0`.
- [ ] Commit/push/tag Quant `v13.27.1.18`, Console `v13.27.1.18-console`, and Docs `v13.27.1.18-docs` only if the stage was reached.

### Task 11: Final audit and delivery

**Files:**
- Create: `reports/advisory_r_workflow/final_acceptance.json`
- Create: `reports/advisory_r_workflow/final_acceptance.md`
- Update: `D:/Codex-Workspace/踩坑日志.txt`.

- [ ] Run final `git diff --check` and clean-status checks in all three worktrees.
- [ ] Verify every reached version has its expected commit, push, and tag; verify skipped versions have explicit hard-stop evidence and no tag.
- [ ] Verify no historical artifact bytes/hash changed and no secret, Trade/Withdraw API, Demo order, Live order, auto ARM, or Live-admission change was introduced.
- [ ] Record all environment/path/encoding/test-run issues in the UTF-8 pitfall log.
- [ ] Deliver reached-stage artifacts, survivor counts, hashes, release/approval/ARM/order state, commits/tags/push state, and known issues.

## Self-Review

- Every bundle requirement maps to a task above; hard-stop branches are explicit.
- No task permits result-after exit-policy changes or a forced survivor.
- Legacy byte/hash parity and unchanged Live admission are tested, not assumed.
- Structure rules are declarative and whitelisted; no arbitrary execution hook is introduced.
- Partial-leg cost allocation, gap handling, null-vs-zero return semantics, and portfolio exceptions are explicit.
- No stage performs a private exchange call, creates an order, or ARMs a runtime.
