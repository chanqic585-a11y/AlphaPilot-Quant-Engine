# Candidate Evidence Closure Locked Validation Implementation Plan

> **For Codex:** Execute with `executing-plans`; use TDD for every behavior change. This is a research-only validation milestone, not execution approval.

**Goal:** Re-evaluate the seven canonical `risk_model_failure` candidate families under an immutable, preregistered protocol that separates signal edge, costs, and account risk, and produces auditable pass/fail/unavailable outcomes without reviving archived versions.

**Architecture:** Add a self-contained `alphapilot.validation` audit layer. It consumes existing full-archive reports and immutable strategy artifacts, builds deterministic candidate and split manifests, evaluates available trade-level evidence, and emits reports. Existing strategy registry, backtest workflow, Console, App, and execution permissions remain unchanged.

**Tooling:** Python 3 via `D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe`, standard library, pandas/numpy already pinned in the repo, pytest, PowerShell.

## Fixed Research Decisions

- Candidate discovery starts from `primaryFailureType=risk_model_failure`; the supplied seven families are assertions, not the sole source.
- Candidate versions are deduplicated by canonical family and immutable definition/signal hashes. Duplicate children never cast independent votes.
- Signal rules, direction, timeframe, thresholds, universe rules, and signal-side exits are frozen before locked evaluation.
- Risk model 1 (`0.25%` per trade) is the sole primary account-path acceptance model. Models 2 and 3 are sensitivity-only; model 0 is signal normalization only.
- NoTrade and a simple directional baseline are reported for context, but cannot grant candidate passage.
- A 1D locked sample with 30-49 trades is exploratory only. Hard evidence requires at least 50 effective trades; 1H requires 80 and 15m requires 150. Effective sample size is reported and can only reduce confidence.
- Point-in-time universe membership, listing/delisting history, and survivorship status are audited. Missing evidence remains `null`/`unavailable`.
- Random operations use registered seeds. The environment fingerprint, checkpoint state, and resource limits are part of the validation manifest.
- No clean locked sample means `locked_sample_unavailable`; pseudo-locked diagnostics cannot pass.
- At most two families can receive `recommend_new_research_version`. No archived version is revived and no execution eligibility is changed.

## Task 1: Input and Candidate Contract

**Files:**
- Create: `tests/validation/test_candidate_selection.py`
- Create: `tests/validation/test_candidate_deduplication.py`
- Create: `alphapilot/validation/__init__.py`
- Create: `alphapilot/validation/candidate_selection.py`
- Create: `alphapilot/validation/candidate_deduplication.py`
- Create: `alphapilot/validation/models.py`

1. Add failing tests that load a minimal failure-attribution fixture and require discovery of only `risk_model_failure` rows.
2. Require family-level canonical representatives and duplicate mappings; A1's two versions must count as one family.
3. Require C-tier prefilter metadata and stable Chinese display labels.
4. Run `python -m pytest tests/validation/test_candidate_selection.py tests/validation/test_candidate_deduplication.py -q` and confirm failure.
5. Implement the smallest typed models, selection, and deduplication logic.
6. Re-run the focused tests.

## Task 2: Immutable Hashes, Freeze, and Split Registry

**Files:**
- Create: `tests/validation/test_signal_freezer.py`
- Create: `tests/validation/test_data_split_registry.py`
- Create: `alphapilot/validation/hashing.py`
- Create: `alphapilot/validation/signal_freezer.py`
- Create: `alphapilot/validation/data_split_registry.py`
- Create: `alphapilot/validation/locked_sample_protocol.py`

1. Add failing tests for canonical JSON hashes, stable signal hashes, immutable cost/risk hashes, and split hash stability.
2. Add contamination tests: selection ranges or symbols overlapping locked ranges/holdbacks must be flagged.
3. Add tests that unreproducible signal definitions stop a candidate rather than inferring logic from its name.
4. Implement stable hashing, freeze records, split manifests, effective-sample rules, and leakage audit.
5. Re-run focused tests.

## Task 3: Preregistration Generator

**Files:**
- Create: `tests/validation/test_preregistration.py`
- Create: `alphapilot/validation/preregistration.py`
- Create: `alphapilot/reports/generate_candidate_evidence_closure_report.py`
- Create: `alphapilot/reports/candidate_evidence_closure_schema.py`
- Create: `scripts/run_candidate_evidence_closure.ps1`
- Generate: `reports/candidate_validation_queue.json`
- Generate: `reports/candidate_deduplication_report.json`
- Generate: `reports/candidate_locked_validation_preregistration.json`
- Generate: `reports/candidate_locked_validation_preregistration.md`

1. Add failing tests requiring candidate list, primary risk model, sensitivity models, baseline definitions, seed registry, environment fingerprint, resource limits, split protocol, and output paths.
2. Implement preregistration generation with atomic writes and a SHA-256 `preRegistrationHash`.
3. Generate the real preregistration from current reports.
4. Verify that missing artifacts are recorded and no missing value is coerced to zero.
5. Run focused tests and `git diff --check`.
6. Commit exactly the preregistration contract: `Register locked candidate evidence validation protocol`.

## Task 4: Signal and Cost Evaluation

**Files:**
- Create: `tests/validation/test_signal_metrics.py`
- Create: `tests/validation/test_cost_stress.py`
- Create: `alphapilot/validation/signal_metrics.py`
- Create: `alphapilot/validation/cost_stress.py`
- Create: `alphapilot/validation/baselines.py`

1. Add failing tests for R-based signal metrics, confidence intervals, PF intervals, NoTrade baseline, simple-signal baseline, and 1x/1.5x/2x immutable costs.
2. Require unavailable funding or MFE/MAE fields to remain `null`.
3. Implement deterministic block bootstrap with at least 5,000 draws in full mode and an injectable lower count for tests.
4. Implement cost attribution and the cost threshold where edge changes sign.
5. Re-run focused tests.

## Task 5: Account Risk and Monte Carlo

**Files:**
- Create: `tests/validation/test_risk_models.py`
- Create: `tests/validation/test_monte_carlo.py`
- Create: `alphapilot/validation/risk_models.py`
- Create: `alphapilot/validation/monte_carlo.py`
- Create: `alphapilot/validation/portfolio_risk.py`

1. Add failing tests for all four registered models and hash immutability.
2. Require primary acceptance to use model 1 only; sensitivity models cannot rescue a failure.
3. Add deterministic block/sequence Monte Carlo tests for drawdown and loss-streak quantiles.
4. Implement account-path simulation with concurrency, symbol, directional-cluster, daily pause, and drawdown stop constraints.
5. Add portfolio concentration and overlap summaries that remain unavailable if timestamps/symbols are missing.
6. Re-run focused tests.

## Task 6: Status Decision and End-to-End Validator

**Files:**
- Create: `tests/validation/test_candidate_status.py`
- Create: `tests/validation/test_candidate_validator.py`
- Create: `alphapilot/validation/candidate_validator.py`
- Create: `alphapilot/validation/status_decision.py`
- Create: `alphapilot/validation/checkpoint.py`

1. Add failing tests for `passed`, `failed_signal`, `failed_cost`, `failed_risk`, `insufficient_sample`, `locked_sample_unavailable`, `signal_unreproducible`, and `prefilter_stopped`.
2. Require C-tier short-circuit before full risk evaluation when its historical prefilter fails.
3. Require duplicate versions not to double-vote and cap new-version recommendations at two.
4. Require checkpoints to resume idempotently using validation identity hashes.
5. Implement orchestration and status decisions.
6. Re-run focused tests.

## Task 7: Execute the Registered Validation

**Files:**
- Generate: `reports/candidate_validation_data_manifest.json`
- Generate: `reports/candidate_validation_cost_models.json`
- Generate: `reports/candidate_validation_risk_models.json`
- Generate: `reports/candidate_signal_layer_report.json`
- Generate: `reports/candidate_locked_sample_report.json`
- Generate: `reports/candidate_walk_forward_report.json`
- Generate: `reports/candidate_cost_stress_report.json`
- Generate: `reports/candidate_risk_model_report.json`
- Generate: `reports/candidate_monte_carlo_report.json`
- Generate: `reports/candidate_portfolio_risk_report.json`
- Generate: `reports/candidate_evidence_closure_report.json`
- Generate: `reports/candidate_evidence_closure_summary.md`
- Generate: `reports/candidate_evidence_closure_leaderboard.csv`
- Generate: `reports/candidate_continue_archive.json`
- Generate: `reports/candidate_new_version_recommendations.json`

1. Run the PowerShell entry with the registered 5,000 bootstrap and 5,000 Monte Carlo draws.
2. Verify all output hashes against preregistration and checkpoint identities.
3. Treat missing clean trade/signal evidence honestly; do not synthesize trades or infer signal rules.
4. Inspect candidate-level outcomes and ensure at most two new-version recommendations.
5. Run the command a second time to verify deterministic resume/idempotence.

## Task 8: Documentation and Verification

**Files:**
- Create: `docs/candidate-evidence-closure-methodology.md`
- Create: `docs/locked-sample-policy.md`
- Create: `docs/signal-vs-risk-validation.md`
- Create: `docs/candidate-evidence-closure-results.md`
- Modify: `README.md`
- Copy prompt to: `D:\Codex-Workspace\AlphaPilot-Docs\prompts\AlphaPilot_Candidate_Evidence_Closure_Locked_Validation_Codex_Prompt_CN.md`
- Modify: `D:\Codex-Workspace\AlphaPilot-Docs\README.md`

1. Document what is proven, unavailable, and prohibited in Chinese.
2. Document point-in-time universe and survivorship limitations.
3. Document that model 1 is primary and models 2/3 are sensitivity-only.
4. Run:
   - `D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m compileall alphapilot`
   - `D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m pytest tests -q`
   - `D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m alphapilot.scripts.validate_config`
   - `powershell -ExecutionPolicy Bypass -File scripts\check_safety.ps1`
   - `git diff --check`
5. Confirm no API key, Trade API, Withdraw API, account, position, order, dry-run, Demo, or live execution capability was added.
6. Commit results: `Add candidate evidence closure validation results`.

## Task 9: Integration and Research Milestone

1. Review the feature branch with `git status`, `git diff --stat`, and the generated summary.
2. Fast-forward the Quant main branch without touching the pre-existing dirty report in the primary checkout.
3. Commit the Docs prompt/readme separately.
4. Push both `main` branches.
5. Only if preregistration, actual validation, traceability, tests, safety checks, and clear status all pass, create the next unused research milestone tag and docs tag. The tag must not imply execution approval.
6. Leave both repositories clean except for the pre-existing Quant report modification that was present before this task.

