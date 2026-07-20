# AlphaPilot Demo Release Replay And Portfolio Rescue Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task by task.

**Goal:** Trace the ten active 1h/1d OKX Demo releases back to their original research evidence, replay their frozen identities on the current local public-data engines, and run one bounded development-only portfolio rescue campaign without changing any Demo release or promotion state.

**Architecture:** A new `demo_release_replay` package reads sanitized immutable contract metadata and the original Quant reports, delegates signal generation to the existing low-frequency and short-cycle engines, and writes replay ledgers plus comparison evidence. A separate `portfolio_rescue` package consumes only those replay ledgers, enforces frozen sleeve and risk-policy identities, and emits development-only portfolio diagnostics. Both tracks are offline, public-data-only, and explicitly barred from creating Release, Demo, or live-trading approval artifacts.

**Tech Stack:** Python 3.13, pandas, pyarrow, pytest, existing AlphaPilot low-frequency/short-cycle engines, JSON/CSV/Parquet evidence.

---

## Task 1: Freeze The Replay Contract And Source Mapping

**Files:**
- Create: `alphapilot/demo_release_replay/__init__.py`
- Create: `alphapilot/demo_release_replay/contracts.py`
- Test: `tests/demo_release_replay/test_contracts.py`

1. Add a failing test with two synthetic Demo contracts proving that contract parsing preserves release hash, candidate identity, timeframe, family, override mode, actor, and bypassed evidence.
2. Add a failing test proving credentials and unknown private fields are not copied into normalized evidence.
3. Run `python -m pytest tests/demo_release_replay/test_contracts.py -q` and confirm RED.
4. Implement immutable replay-contract dataclasses and a bounded directory loader.
5. Re-run the test and confirm GREEN.

## Task 2: Build Targeted 1d And 1h Replay Adapters

**Files:**
- Create: `alphapilot/demo_release_replay/adapters.py`
- Create: `alphapilot/demo_release_replay/replay.py`
- Test: `tests/demo_release_replay/test_replay.py`

1. Add failing synthetic-fixture tests for a frozen 1d candidate and a frozen 1h asset-filtered candidate.
2. Prove next-bar entry, fee/slippage accounting, selected-pair preservation, split metrics, and deterministic trade ledgers.
3. Prove no adapter can emit `release`, `approved_for_demo`, or `live` status.
4. Run the targeted test and confirm RED.
5. Implement adapters around the existing low-frequency and short-cycle research functions without changing those engines.
6. Re-run and confirm GREEN.

## Task 3: Emit Replay Provenance And Comparison Evidence

**Files:**
- Create: `alphapilot/demo_release_replay/evidence.py`
- Create: `alphapilot/scripts/run_demo_release_replay.py`
- Test: `tests/demo_release_replay/test_evidence.py`

1. Add failing tests for exactly ten normalized releases, per-candidate Parquet ledgers, original-versus-replay comparison rows, an artifact manifest, and explicit `research_replay_only` status.
2. Implement JSON/CSV/Markdown/Parquet writers with SHA-256 inventory.
3. Run tests and confirm GREEN.
4. Execute the CLI against:
   - Console contracts: `D:/Codex-Workspace/AlphaPilot-Control-Console/data/demo_release_contracts`
   - 1d source report: `D:/Codex-Workspace/AlphaPilot-Quant-Engine/reports/v13_7_20_five_strategy_candidate_factory_report.json`
   - 1h source report: `D:/Codex-Workspace/AlphaPilot-Quant-Engine/reports/v13_7_40_short_cycle_parameter_search_binance_vision_asset_filtered_report.json`
   - OKX local data: `D:/Codex-Workspace/AlphaPilot-Quant-Engine/user_data/data/okx/futures`
   - Binance Vision local data: `D:/Codex-Workspace/AlphaPilot-Quant-Engine/user_data/data/binance_vision/futures`
   - Output: `reports/demo_release_replay/v13_27_1_46_20260720`
5. Verify candidate count, hashes, coverage, failures, and current replay metrics without mutating Console state.

## Task 4: Freeze A Bounded Portfolio Rescue Campaign

**Files:**
- Create: `alphapilot/portfolio_rescue/__init__.py`
- Create: `alphapilot/portfolio_rescue/contracts.py`
- Test: `tests/portfolio_rescue/test_contracts.py`

1. Add failing tests for a fixed three-sleeve maximum, representative-only family deduplication, fixed policy objects, six-to-eight trial budget, no result-driven parameter mutation, and no Formal/OOS claim.
2. Freeze sleeve selection from pre-existing source rank and mechanism distinctness, not from new replay results.
3. Implement stable hashes for campaign, sleeve, and policy identities.
4. Confirm GREEN.

## Task 5: Run Development-Only Portfolio Rescue Diagnostics

**Files:**
- Create: `alphapilot/portfolio_rescue/replay.py`
- Create: `alphapilot/portfolio_rescue/evidence.py`
- Create: `alphapilot/scripts/run_portfolio_rescue.py`
- Test: `tests/portfolio_rescue/test_replay.py`

1. Add failing tests for chronological merge, pair cooldown, max concurrent positions, same-direction cap, per-sleeve contribution, cost stress, monthly concentration, and no lookahead from unknown exits.
2. Implement replay over the Task 3 ledgers with at most eight frozen policy trials.
3. Emit `campaign_summary.json/md`, `policy_matrix.csv`, `sleeve_attribution.csv`, `monthly_consistency.csv`, `failure_attribution.json`, `experiment_budget.json`, preregistration identity, and artifact manifest.
4. Mark all outcomes `development_only`; `formalCandidateCount`, `releaseCount`, and `lockedOosReadCount` must remain zero.
5. Run the campaign into `reports/portfolio_rescue/v13_27_1_46_20260720` and report whether any portfolio warrants a future fresh preregistered OOS campaign.

## Task 6: Verify, Package, And Commit Locally

**Files:**
- Create: `reports/v13_27_1_46_closeout.md`
- Create: `reports/v13_27_1_46_artifact_manifest.json`

1. Run targeted tests for both new packages.
2. Run `python -m compileall alphapilot`.
3. Run the repository safety/config checks.
4. Run `git diff --check`.
5. Package evidence under `D:/Codex-Workspace/artifacts/AlphaPilot_V13.27.1.46_Demo_Replay_Portfolio_Rescue_Evidence_20260720.zip`.
6. Commit locally with `Add V13.27.1.46 Demo replay and portfolio rescue evidence`.
7. Do not push without fresh explicit authorization.
