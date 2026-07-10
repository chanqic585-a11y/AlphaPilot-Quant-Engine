# AlphaPilot V13.16-V13.22 Implementation Plan

## Execution Rules

- Execute phases in order and commit each accepted checkpoint.
- Do not cross a failed evidence gate.
- Preserve `D:\Codex-Workspace\回测数据` as read-only raw input.
- Keep default reward/risk target at or above `2R`.
- Keep Live and Withdraw disabled throughout engineering validation.
- Never count `legacy_synthetic` samples as formal evidence.

## Phase 1: V13.16 Data Foundation

1. Add `alphapilot/data_foundation/` domain modules for catalog types, discovery, quality validation, canonicalization, checkpoints, public incremental collection, and snapshot registration.
2. Fix the existing XLSX timestamp parser to prefer `timestamp_ms` and safely convert Excel serial dates only as fallback.
3. Change import defaults from historical Baidu paths to `D:\Codex-Workspace\回测数据` while retaining explicit CLI overrides.
4. Classify annual/ALL duplicate families, checkpoint files, timestamped duplicate exports, unknown provenance, and unconfirmed tails.
5. Add atomic write and resume manifests.
6. Add smoke and failure tests for CSV/XLSX parsing, time conversion, duplicate classification, OHLC validation, gaps, unconfirmed rows, and resume behavior.
7. Generate a complete catalog report and a BTC/ETH/SOL canonical smoke snapshot.
8. Register the smoke DataSnapshot in `data/evolution_registry.sqlite`.
9. Update README and Docs.
10. Run checks and commit V13.16.

## Phase 2: V13.17 FactorRun and Backtest

1. Add a materialized feature-matrix builder tied to DataSnapshot files.
2. Implement approved point-in-time indicators and DSL expression evaluation.
3. Add `>=2R` next-bar labels with conservative same-bar ambiguity handling.
4. Persist feature/label artifacts with hashes and register completed FactorRuns.
5. Build purged walk-forward Experiment records and cost stress outputs.
6. Train deterministic logistic and tree-stump challenger models only from registered FactorRuns.
7. Register models and formal StrategyCandidates only when hard evidence is complete.
8. Add leakage, reproducibility, cost, concentration, and locked-test tests.
9. Run a BTC/ETH/SOL smoke experiment before wider-universe batches.
10. Update reports/docs and commit V13.17.

## Phase 3: V13.18 Historical Path Replay

1. Add an event-time replay engine using canonical bars.
2. Implement next-bar fill, persistent position state, target/stop, timeout, fee, funding, slippage, MFE, and MAE.
3. Mark existing deterministic sandbox outcomes as `legacy_synthetic` and exclude them from formal totals.
4. Create immutable replay Outcome Ledger records and reports.
5. Connect the console local-simulation contract to replay evidence without duplicating strategy stages.
6. Add deterministic replay and no-lookahead tests.
7. Run locked-window smoke replay and commit V13.18.

## Phase 4: V13.19 Real-Time Local Forward

1. Add a frozen-release forward runner consuming public real-time market data only.
2. Persist open positions, restart state, collection gaps, signals, rejections, and outcomes.
3. Keep a 1000 USDT virtual account and the approved fixed risk envelope.
4. Separate historical replay from real-time forward evidence in registry and console contracts.
5. Add auto-start/resume controls without fabricating downtime samples.
6. Add Outcome Ledger and daily report tests.
7. Start forward observation for eligible releases and commit V13.19.

## Phase 5: V13.20 OKX Demo

1. Require an immutable DemoRelease before strategy automation can start.
2. Connect release scanner, arbitration, data/liquidity gates, Demo order lifecycle, protective exits, reconciliation, drift pause, and rollback.
3. Keep runtime credentials process-only and Live/Withdraw locked.
4. Add full Demo observability and report contracts.
5. Run no-key and read-only failure-closed tests plus connectivity smoke only when runtime credentials are supplied.
6. Start formal Demo observation only after release eligibility and commit V13.20.

## Phase 6: V13.21 Live Safety Candidate

1. Extend immutable LiveCandidate evidence and approval contracts.
2. Implement the live safety plane in disabled mode: private-state adapter boundary, idempotency, request expiry, price/instrument checks, reconciliation, restart recovery, circuit breakers, and kill switch.
3. Prove that approval alone does not enable execution and no adapter can run without exact release/risk binding.
4. Add operator and mobile review summaries.
5. Commit V13.21 without enabling real orders.

## Phase 7: V13.22 Offline Evolution Loop

1. Add evidence-classed Outcome Ledger ingestion for replay, forward, Demo, and future Live.
2. Add failure-mode attribution, factor-decay reports, and offline research triggers.
3. Run bounded factor generation, correlation filtering, champion/challenger comparison, and new candidate registration.
4. Verify that no challenger can mutate or replace a running release directly.
5. Add end-to-end lineage and rollback tests.
6. Commit V13.22.

## Final Verification

1. Run all Quant Engine tests and compileall.
2. Run config validation and safety scans.
3. Run canonical-data, FactorRun, backtest, replay, forward-contract, Demo-contract, Live-candidate, and evolution smoke pipelines.
4. Run Control Console tests, HTTP contract smoke, Node syntax checks, and UI checks for stable lifecycle labels.
5. Run mobile typecheck and Expo public config checks if its contracts changed.
6. Run `git diff --check` and verify worktree status in all modified repositories.
7. Commit and push each repository only after its checks pass.
8. Stop completed background jobs, verify checkpoints and reports, and only then perform an automatic system shutdown if no forward or Demo collector is intended to remain active.
