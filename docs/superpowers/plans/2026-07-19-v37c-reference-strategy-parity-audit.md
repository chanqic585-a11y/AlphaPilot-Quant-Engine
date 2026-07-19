# V37C Reference Strategy Parity Audit Implementation Plan

> Execute in `D:\Codex-Workspace\AlphaPilot-Quant-V37C-parity-worktree` on branch `feature/v13.27.1.37c-reference-strategy-parity-audit`. Use `D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe` and the bundled Git runtime.

**Goal:** Determine whether V37B failures came from source translation, executable drift, impossible gates, or genuinely weak OOS economics without changing any frozen V37B result.

**Architecture:** Add a metadata-only source semantic audit, expose production signal fingerprints, compare them with an independent oracle, prove gate reachability with known-positive events, correct failure attribution, and generate a hash-checked offline V37C evidence bundle.

**Tech stack:** Python 3, pandas, NumPy, PyArrow/Parquet, pytest, existing AlphaPilot campaign and evidence utilities.

---

## Task 1: Correct Failure Attribution Without Changing Gates

**Files:**
- Modify: `tests/research_screening/test_campaign_runner.py`
- Modify: `alphapilot/research_screening/campaign_runner.py`

1. Add a failing test showing that a prescreened candidate with failed base gates and no translation must report both `freqtrade_translation_not_executed` and `out_of_sample_failed`.
2. Run the focused test and verify the expected failure.
3. Change `_failure_labels` so OOS failure is independent of translation status.
4. Add `economicBasePassed` to campaign candidate rows while preserving the existing end-to-end `basePassed` definition.
5. Run the focused test and existing campaign-runner tests.
6. Commit: `Fix V37C reference campaign failure attribution`.

## Task 2: Expose Production Signal Fingerprints

**Files:**
- Modify: `tests/reference_strategy_research/test_signals.py`
- Modify: `alphapilot/reference_strategy_research/signals.py`

1. Add failing tests for a public `detect_reference_candidate_signals` API on deterministic UTC-range and second-entry fixtures.
2. Verify the tests fail because the API does not exist.
3. Add a frozen `ReferenceSignal` contract and detector returning signal/entry positions, timestamps, entry price and risk distance.
4. Refactor event replay to consume the public detector without changing exit behavior.
5. Run signal and exit-policy tests.
6. Commit: `Expose reference strategy signal fingerprints for parity audit`.

## Task 3: Add Independent Oracle and Parity Checks

**Files:**
- Add: `tests/reference_strategy_research/test_parity_audit.py`
- Add: `alphapilot/reference_strategy_research/parity_audit.py`

1. Add failing tests requiring independent oracle parity for both mechanisms and both directions on synthetic fixtures.
2. Verify failure before implementation.
3. Implement oracle functions without importing production private helpers.
4. Compare exact positions/timestamps and tolerance-bounded numeric fields.
5. Add a real-partition parity function that reads registered BTC 1H and 4H Parquet files and reports provenance.
6. Run focused parity tests.
7. Commit: `Add independent V37C signal parity oracle`.

## Task 4: Add Source Semantics and Lineage Audit

**Files:**
- Add: `tests/reference_strategy_research/test_source_semantics.py`
- Add: `alphapilot/reference_strategy_research/source_semantics.py`

1. Add a synthetic package fixture containing bounded MQL and documentation samples plus expected hashes.
2. Add failing tests for hash verification, source-equivalence classification and no-source-text output.
3. Implement in-memory ZIP inspection for selected source files only.
4. Record hashes, bounded metadata, citations, material translation gaps and classifications.
5. Classify third-party-use claims as insufficient evidence unless comparable audited performance evidence exists.
6. Run focused tests.
7. Commit: `Add V37C source semantic lineage audit`.

## Task 5: Prove Gate Reachability

**Files:**
- Extend: `tests/reference_strategy_research/test_parity_audit.py`
- Extend: `alphapilot/reference_strategy_research/parity_audit.py`

1. Add a failing test that creates known-positive development, walk-forward and holdout events under the unchanged preregistration.
2. Verify the test fails before the helper exists.
3. Implement deterministic positive-event construction and evaluate it through `evaluate_candidate_gates`.
4. Assert sample, prescreen, base and formal gates all pass and record every observed threshold.
5. Run focused tests.
6. Commit: `Prove V37B campaign gates are reachable`.

## Task 6: Build the Offline V37C Audit Runner

**Files:**
- Add: `tests/reference_strategy_research/test_v37c_runner.py`
- Add: `alphapilot/scripts/run_v37c_reference_strategy_parity_audit.py`
- Modify: `alphapilot/reference_strategy_research/__init__.py` only if public exports are useful

1. Add an integration test with a temporary package, frozen V37B-like artifacts and small Parquet fixtures.
2. Verify the runner test fails before implementation.
3. Implement CLI arguments for repo, package and V37B run directory; do not hardcode user paths.
4. Verify package hash, V37B selected-candidate hash, implementation evidence hashes and input artifact hashes.
5. Generate source audit, gap matrix, synthetic and real parity, gate reachability, reassessment, conclusion and manifest.
6. Verify that the manifest hashes every output and that the runner performs no network or runtime mutations.
7. Run focused integration tests.
8. Commit: `Add V37C reference strategy audit runner`.

## Task 7: Generate and Verify the Frozen Audit Bundle

**Files:**
- Add: `reports/backtest_screening/reference_strategy_parity/<runId>/*`

1. Run V37C against the real supplied package and frozen V37B run.
2. Confirm source classifications, production-oracle parity and gate reachability.
3. Confirm the V37B reassessment distinguishes source-equivalence limits from OOS economic failure.
4. Hash and verify all artifacts.
5. Confirm no V37B artifact changed by checking Git and manifest hashes.

## Task 8: Full Validation and Delivery

1. Run targeted tests:
   `python -m pytest --import-mode=importlib tests/reference_strategy_research tests/research_screening/test_campaign_runner.py tests/research_screening/test_campaign_metrics.py -q`
2. Run full tests:
   `python -m pytest --import-mode=importlib tests -q`
3. Run compile check:
   `python -m compileall alphapilot`
4. Run configuration validation and the repository safety script if present.
5. Run bounded safety scan for credentials, private exchange calls, Withdraw, order creation and Demo/Live mutations.
6. Run `git diff --check` and inspect final status.
7. Commit generated evidence and closeout.
8. Push the feature branch only after all checks pass.

## Stop Conditions

- Do not alter V37B artifacts or preregistration.
- Do not download data or access exchange APIs.
- Do not weaken gates, optimize parameters, force a pass or create a Release.
- Stop and report if a frozen hash does not match.
- A parity mismatch is a valid audit result; preserve it instead of modifying the oracle to agree.
