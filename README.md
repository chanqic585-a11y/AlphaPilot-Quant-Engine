# AlphaPilot Quant Engine

## Bounded Structural Redesign Loop

When bounded parameter optimization classifies a formal research result as
structurally weak, AlphaPilot may create one immutable child from a registered,
deterministic strategy recipe. The failed parent is archived only in the same
SQLite transaction that registers the child, queues its backtest, and appends
the redesign audit records. A retry returns the same child instead of creating
duplicates.

Structural generations are limited to `1/3`, `2/3`, and `3/3`. This budget is
separate from the existing three-attempt parameter-optimization budget. Recipe
selection uses development and walk-forward evidence only; holdout and locked
validation metrics are excluded. Missing data, network, and worker failures do
not trigger redesign, and no strategy is forced through a failed gate.

Recovery is explicit and idempotent:

```powershell
python -m alphapilot.evolution.workflow.cli `
  --registry data/evolution_registry.sqlite `
  recover-structural-redesigns
```

Before its first recovery mutation, the command creates an online SQLite backup
under the registry's sibling `backups/` directory. Generated children remain in
the existing serial formal-backtest queue; the feature does not add another
formal worker. Every generated strategy remains research-only with
`targetR >= 2R`. Backtest, Local Forward, immutable OKX Demo Release, Demo risk,
and Live approval gates are unchanged. No API credential, Withdraw capability,
or order permission is introduced.

## Bounded Auto-Optimization and 2R Trend Runner

Failed strategy-performance backtests can now enter one audited optimization
campaign. The campaign creates immutable Challenger versions, changes one
allowlisted parameter per attempt, and drains at most three attempts through
the normal formal worker queue. Operational/data failures stop immediately;
structurally weak candidates stop early; exhausted candidates remain failed.
No result is force-passed.

Parameter selection reads only development and walk-forward summaries. Holdout
and locked-OOS values are excluded from the Challenger result payload and audit
decision. A selected Challenger receives one formal locked validation; that
formal result is not fed back into another tuning round.

Automatically optimized Challengers use `two_r_half_atr_runner_v1`: close 50%
at the first gross `+2R` target, then manage the remainder with a confirmed-bar
ATR14 x2.5 trailing stop and a `+1R` floor. This can realize less or more than
2R for the complete trade; for example, half at +2R and half at +1R is +1.5R
gross before fees, slippage, and funding. Existing fixed-target strategy
versions retain their original immutable behavior.

This workflow creates no Demo/Live release, stores no credential, and grants no
order permission. See
`docs/superpowers/specs/2026-07-14-bounded-auto-optimization-trend-runner-demo-diagnostics-design.md`.

## V13.27.8 Shared Official Market Data

V13.27.8 makes verified OKX public OHLCV a shared warehouse asset instead of
downloading the same instrument and timeframe again for every strategy data
contract. A new contract first runs its existing local-data research smoke,
then resolves the newest canonical partition whose manifest identity, path,
file and SHA-256 all pass validation.

When a verified base exists, the collector requests only confirmed candles
newer than the base cutoff. An empty tail reuses the original immutable file;
a non-empty tail is merged with the base and written as a new validated
canonical snapshot. Invalid manifests and partial page checkpoints are never
reused as formal evidence.

The rule applies uniformly to `5m`, `15m`, `1h`, `4h`, `1d` and future
supported periods. Strategy workflows may wait in the durable queue together,
while one physical downloader remains serial to avoid OKX rate-limit
contention. Strategy definitions, target R, promotion gates and trading
permissions are unchanged.

See `docs/V13.27.8-shared-official-market-data.md`.

## V13.27.6 Demo Runtime Resume and Official Data Progress

V13.27.6 adds persisted page-level telemetry for long OKX official-data
downloads. Workflow projection now exposes the active instrument, timeframe,
requested pages, collected K-lines, page budget, timestamp, and percentage
while retaining the existing phase progress.

The active page checkpoint is operational telemetry only. Partial rows are not
registered as a completed partition and never count as formal backtest
evidence. Demo ordinary-pause recovery is implemented in Control Console and
does not change Quant strategy logic, target R, or execution permissions.

See `docs/V13.27.6-official-data-progress.md`.

## V13.27.5 Cancelled Attempt Resume and Serial Queue Lock

V13.27.5 separates a reversible pause from an irreversible cancellation.
Queued backtests can now be paused and resumed. A cancelled attempt can create
one idempotent successor from the saved checkpoint while the cancelled attempt
remains immutable in the audit history.

One process-wide batch lock prevents duplicate serial workers from executing
different runs at the same time. The active batch also drains newly queued
backtests after each run, so a restarted attempt joins the durable queue
without creating a competing worker.

Pausing during official-history collection no longer marks that phase as
complete. Resume re-enters the same phase and continues from the persisted
partition checkpoint instead of validating a paused partial result. One-click
starts also obey the process-wide batch lock, so repeated clicks cannot create
parallel OKX download workers.

Formal data collection can still take a long time by design. Each strategy
requests its declared timeframe plan across the collection-time, public
liquidity-ranked Top50 crypto USDT-swap universe from 2020 onward, while OKX
history-candles returns at most 100 bars per request. A
5-minute partition therefore needs thousands of public requests per symbol;
the durable partition counter may remain unchanged until the current
symbol/timeframe partition finishes.

See docs/V13.27.5-cancelled-attempt-resume.md.

## V13.27.4 Workflow Recovery and Demo Release

V13.27.4 makes workflow state match the real worker state. Official OKX history
collection checks pause/cancel before every page, a resumed task waits for the
old worker lock to be released, and all selected backtests enter the visible
queue before one serial worker processes them in order.

A formal backtest pass continues to start the first public local-forward cycle
automatically. Local-forward results now retain the immutable
`strategyCandidateId`, allowing the Control Console to create an audited
Demo-only release without name matching or fabricated samples.

See `docs/V13.27.4-workflow-recovery-demo-release.md`.

## V13.27.3 Short-Cycle Workflow Candidate Pack

V13.27.3 registers ten executable research candidates: five 5-minute and five
15-minute strategies. Registration is idempotent and creates only immutable
StrategyVersion records plus awaiting backtest runs.

Formal backtests use the collection-time, public liquidity-ranked Top50 OKX
crypto USDT perpetual universe. This is not a reconstructed historical
point-in-time universe; single-symbol runs are smoke/debug only. Promotion still requires
`targetR >= 2`, fees, slippage, funding, delay, purged walk-forward, locked OOS,
and unseen-symbol evidence.

Selected backtests and public local-forward cycles run serially. Local forward
uses completed public candles, preserves a separate release/session/ledger per
strategy, and never creates an exchange order.

See `docs/V13.27.3-short-cycle-workflow-candidate-pack.md`.

## V13.27.1.6 Resumable Workflow Worker

V13.27.1.6 adds a run-scoped cross-process worker lock for the dual-layer
backtest CLI. A Control Console restart can safely launch the same workflow run:
the first worker owns the lock, duplicate workers return without mutating the
run, and a later process continues from the persisted workflow and official-data
checkpoints. Explicitly paused runs remain paused until the user resumes them.

See `docs/V13.27.1.6-resumable-workflow-worker.md`.

AlphaPilot Quant Engine is the future backend research and execution-control layer for AlphaPilot.

Current version:

```text
AlphaPilot V13.27.11 - Formal Backtest Performance and Reliability
```

## V13.27.11 Formal Backtest Performance

The fixed-2R evaluator now prepares each immutable execution and funding path
once per instrument. Repeated signals use binary timestamp lookup and the same
conservative stop-first candle rules, fees, slippage, funding, latency, MFE and
MAE formulas. This is a calculation-path optimization only; formal evidence and
gate semantics are unchanged.

Run the deterministic parity and performance benchmark with:

```powershell
.venv\Scripts\python.exe scripts\benchmark_formal_fixed_r_path.py
```

The benchmark fails if result hashes differ or if the prepared path is less
than 10x faster than repeated frame preparation. Local validation on 120,000
candles and 600 signals produced identical results and more than 70x speedup;
actual end-to-end runtime also depends on strategy signal generation,
snapshot loading, storage and machine load.

Selected backtest batches use a bounded two-channel pipeline: one worker runs
the memory-heavy snapshot freeze and formal backtest, while one independent
worker prepares and validates public OKX data for the next queued strategy.
This lets the next strategy reuse the canonical warehouse and fill only a
missing or latest tail without waiting for the current formal calculation.
Snapshot freezing remains on the formal worker so two large Parquet datasets
are never loaded into memory at the same time.

Official-data progress distinguishes `initial_download`,
`shared_incremental_refresh`, `contract_checkpoint_reuse`, and
`shared_cache_ready`. A strategy-specific progress counter therefore describes
binding and validating its data contract; it does not imply that identical
exchange/timeframe partitions are downloaded again.

## Positioning

V13.4 prepares real Freqtrade smoke backtest execution and report export on top of the V13.3 strategy implementation.

It is separate from the AlphaPilot Mobile App. The mobile app remains the phone-side AI control panel and manual trade record interface. This repository is the backend quant foundation.

## Safety Boundary

V13.4 does not perform live trading.

- No real Trade API.
- No Withdraw API.
- No real API Key storage.
- No real account reads.
- No real position reads.
- No real order creation.
- No automatic trading.
- No real dry-run execution.
- No public REST API exposure.

All configs are templates for research, backtest preparation, or future dry-run design. Never commit real exchange credentials.

## V13.22.0 Offline Evolution Feedback Loop

V13.22 closes the engineering loop from immutable outcomes back into bounded,
offline research. Historical path replay, real-time local forward, OKX Demo,
and future Live outcomes remain separate evidence classes. Probe and synthetic
records are quarantined and cannot trigger factor generation or promotion.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_22_offline_evolution.ps1
```

The loop computes failure attribution, fixed-2R target/stop behavior, cost drag,
concentration, and chronological factor-decay diagnostics. Formal evidence can
create research triggers, bounded shadow factor mutations, correlation review,
champion/challenger review, and fully validated shadow StrategyCandidates.
It cannot mutate or replace a running release and cannot create Demo/Live
releases or orders.

The actual registry currently contains 676 `historical_path_replay_probe`
records and zero formal feedback outcomes. The real V13.22 report therefore
quarantines all 676 records and remains `blocked_no_formal_feedback_evidence`;
it registers no new candidate and changes no release.

Artifacts:

- `alphapilot/evolution/offline/`
- `alphapilot/reports/generate_v13_22_offline_evolution_report.py`
- `reports/v13_22_offline_evolution_report.json`
- `reports/v13_22_offline_research_triggers.json`
- `docs/V13.22.0-offline-evolution-feedback-loop.md`

## V13.21.0 Live Safety Candidate Boundary

V13.21 converts only a checksum-bound, fully validated Demo release into an
immutable Live review candidate. Demo evidence must include at least 50 closed
trades and 30 calendar days, net profit factor >= 1.15, drawdown below 5%,
matched ledgers/checksums, stable symbol/regime/time slices, and no unresolved
critical drift. The proposed risk budget is capped at 1000 USDT, 0.25% per
trade, 250 USDT per order, three concurrent positions, and 2x leverage.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_21_live_safety_candidate.ps1
```

The current registry has no validated Demo release, so the real report is
`blocked_no_validated_demo_release` and exports no Live candidate package.
Manual candidate approval remains review-only: there is no Live adapter, no
execution approval, no credential storage, no account access, and no Withdraw
path.

Artifacts:

- `alphapilot/reports/generate_v13_21_live_safety_candidate_report.py`
- `reports/v13_21_live_safety_candidate_report.json`
- `reports/v13_21_live_safety_readiness_contract.json`
- `docs/V13.21.0-live-safety-candidate-boundary.md`

## V13.20.0 Immutable-Release-Gated OKX Demo

V13.20 converts completed research and real-time local forward evidence into an
immutable OKX Demo release only when every fixed hard gate passes. The release
binds the StrategyCandidate, code/data/model checksums, forward sample count,
calendar coverage, cost and concentration tests, and a 1000 USDT risk envelope.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_20_okx_demo_release.ps1
```

Eligible releases are exported as checksum-protected
`demo_release_contract_<id>.json` files for AlphaPilot Control Console. The
console accepts no externally supplied automatic signal: it scans the frozen
release against OKX public candles and public instrument metadata, sizes inside
the immutable envelope, reconciles Demo balance/positions, applies arbitration
and drift guards, and then uses the existing idempotent Demo-only lifecycle.

The current registry contains no formal StrategyCandidate, ForwardRelease, or
closed real-time forward evidence. The real V13.20 report therefore remains
`blocked_no_formal_strategy_candidate`, writes no DemoRelease contract, and
cannot create an order.

Key paths:

- `alphapilot/reports/generate_v13_20_okx_demo_release_report.py`
- `reports/v13_20_okx_demo_release_report.json`
- `reports/v13_20_okx_demo_readiness_contract.json`
- `docs/V13.20.0-immutable-release-gated-okx-demo.md`

Runtime Demo credentials remain process-only in Control Console. V13.20 does
not store credentials, enable Withdraw, access Live, or promote to Live.

## V13.19.0 Real-Time Local Forward Observation

V13.19 adds a restart-safe, event-sourced forward runner that consumes only
confirmed OKX public candles. A frozen eligible release may create pending
research signals at a completed candle, enter virtually at the next candle
open, and follow `1R` stop / `2R` target paths inside a 1000 USDT virtual
account. It never creates an exchange order.

```powershell
# One public-market observation cycle.
powershell -ExecutionPolicy Bypass -File scripts\run_v13_19_local_forward.ps1

# Resume-safe loop. Missing downtime bars remain explicit collection gaps.
powershell -ExecutionPolicy Bypass -File scripts\run_v13_19_local_forward.ps1 -Loop -PollSeconds 60
```

Registry migration 3 adds immutable `ForwardReleases`, `ForwardSessions`, and
`ForwardEvents`. State checkpoints persist pending signals, open virtual
positions, equity, costs, and last-seen candle times. Closed paths enter the
shared Outcome Ledger with evidence class `realtime_local_forward`; historical
replay and forward evidence are never mixed.

The current real registry has no formal StrategyCandidate and therefore no
candidate-bound historical replay or immutable ForwardRelease. The V13.19
runtime correctly reports `blocked_no_eligible_forward_release` and performs
no network polling. Test fixtures validate next-bar fills, 2R exits, gap
recording, restart recovery, accounting, and fail-closed release creation.

Key paths:

- `alphapilot/evolution/forward/`
- `reports/v13_19_local_forward_report.json`
- `reports/v13_19_local_forward_contract.json`
- `docs/V13.19.0-real-time-local-forward-observation.md`

V13.19 does not use API keys, read exchange accounts or positions, call Trade
API or Withdraw API, create orders, or enable Demo/Live execution. Forward
time cannot be accelerated and downtime observations are never fabricated.

## V13.18.0 Actual-Candle Historical Path Replay

V13.18 adds an event-time replay engine over immutable canonical candles. It
supports next-bar fills, persistent position intervals, `1R` stops, `2R`
targets, conservative same-bar ambiguity, timeouts, fees, slippage, optional
funding, MFE/MAE, same-instrument conflicts, and portfolio concurrency limits.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_18_historical_path_replay.ps1
```

Replay outcomes are immutable rows in the evolution registry `OutcomeLedger`
and a checksum-bound Parquet artifact under ignored `data/market/replay/`.
Existing precomputed-return sandbox evidence is explicitly classified as
`legacy_synthetic` and excluded from formal training and profitability claims.

Because V13.17 created no formal StrategyCandidate, the current real-data run
uses fixed-cadence alternating signals only as an engine probe. It closed 338
actual candle paths and wrote 338 Outcome Ledger rows, but these results are not
a strategy backtest and cannot be promoted. The console contract reports
`engine_ready_waiting_formal_candidate`.

Key paths:

- `alphapilot/evolution/replay/`
- `reports/v13_18_historical_path_replay_report.json`
- `reports/v13_18_historical_replay_contract.json`
- `docs/V13.18.0-actual-candle-historical-path-replay.md`

V13.18 is local historical research only. It does not use API keys, private
exchange endpoints, account state, Trade API, Withdraw API, orders, Demo
releases, or Live execution.

## V13.17.0 Point-in-Time FactorRun and Backtest

V13.17 materializes ten approved factor expressions from an immutable
DataSnapshot, creates next-bar directional labels with a `1R` stop and `2R`
target, and evaluates deterministic logistic and boosted-stump challengers.
Signals are decided at completed bar `t`; entry is the next bar open. If one
OHLC bar touches both stop and target, the label records the stop first.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_17_factor_run_backtest.ps1
```

The development sample uses purged walk-forward folds with an embargo. The
last 20% of timestamps remain locked until the fixed model-selection rule has
chosen the lower-Brier challenger. Baseline, 2x, 3x, one-bar-delay, and extreme
gap cost scenarios are recorded, together with pair/month concentration and
multiple-testing evidence.

The current composite snapshot still contains a local historical base whose
authoritative source manifest is missing. V13.17 therefore permits an
engineering research smoke run but keeps formal promotion blocked. Completed
FactorRuns and shadow-only models may be registered; no StrategyCandidate,
DemoRelease, Live candidate, or order is fabricated around the blocker.

The current fixed-threshold smoke run materialized 40,346 rows over 14,223
timestamps and four OOS folds. It registered ten FactorRuns, two completed
Experiments, and two shadow-only models. The long model generated one OOS
observation and zero locked observations; the short model generated none, so
the performance gate also failed and StrategyCandidate count remains zero.

Key paths:

- `alphapilot/evolution/factor_runs/`
- `reports/v13_17_factor_run_backtest_report.json`
- `reports/v13_17_factor_run_backtest_summary.md`
- `docs/V13.17.0-point-in-time-factor-run-and-backtest.md`

This phase uses local/public market data only. It does not use API keys, read
accounts or positions, call Trade API or Withdraw API, create orders, or
enable Demo/Live execution.

## V13.16.0 Auditable Market Data Foundation

V13.16.0 starts the evidence-first rebuild required before FactorRun, machine
learning, replay, forward observation, Demo, or Live release work can be
trusted. The original files under `D:\Codex-Workspace\回测数据` remain
read-only. Canonical Parquet files, checkpoints, immutable snapshot manifests,
and local registry rows are generated under `data/market/` and the existing
evolution registry.

```powershell
# Build the raw catalog and BTC/ETH/SOL canonical smoke base.
powershell -ExecutionPolicy Bypass -File scripts\build_v13_16_data_foundation.ps1

# Resume-safe full SHA-256 catalog for all raw files.
powershell -ExecutionPolicy Bypass -File scripts\build_v13_16_data_foundation.ps1 -HashMode all

# Or run the full hash as a detached, auditable background job.
powershell -ExecutionPolicy Bypass -File scripts\start_v13_16_full_hash_job.ps1
powershell -ExecutionPolicy Bypass -File scripts\get_v13_16_full_hash_job_status.ps1

# Seed source-verified metadata sidecars for existing canonical smoke files.
powershell -ExecutionPolicy Bypass -File scripts\seed_v13_16_canonical_metadata.ps1

# Collect public-only OKX increments for 15m / 1h / 4h / 1d.
powershell -ExecutionPolicy Bypass -File scripts\collect_v13_16_public_increment.ps1

# Verify base/increment continuity and register one composite snapshot.
powershell -ExecutionPolicy Bypass -File scripts\build_v13_16_composite_snapshot.ps1
```

Current smoke evidence covers BTC, ETH, and SOL perpetual public candles over
four timeframes. All 12 canonical groups are continuous; the composite
snapshot contains the local base plus verified OKX public increments. Repeating
the increment command uses the latest saved cutoff and does not download the
same rows again. Canonical metadata sidecars bind the source and Parquet
checksums to the recorded quality result, so unchanged source files can be
verified without reopening multi-year XLSX exports on every run.

The local base resembles OKX exports but has no authoritative source, license,
download-time, or checksum manifest. It is therefore recorded as unverified
provenance and remains a hard formal-promotion blocker. No missing provenance
is inferred or fabricated. The default strategy reward/risk requirement stays
at or above `2R`, but V13.16 creates no strategy, FactorRun, model, Demo release,
Live candidate, or order.

Key paths:

- `alphapilot/data_foundation/`
- `reports/v13_16_data_foundation_report.json`
- `reports/v13_16_public_increment_report.json`
- `reports/v13_16_public_increment_idempotency_report.json`
- `reports/v13_16_composite_data_snapshot_report.json`
- `reports/v13_16_canonical_metadata_seed_report.json`
- `docs/V13.16.0-auditable-market-data-foundation.md`

V13.16.0 uses local files and unauthenticated public market endpoints only. It
does not use API keys, read exchange accounts or positions, call Trade API or
Withdraw API, create orders, or enable Live execution.

## V13.15.0 Live Candidate Boundary

V13.15.0 can turn a checksum-verified, fully validated Demo release into an
immutable `LiveCandidatePackage`. It does not implement a live exchange
adapter and does not enable execution.

The package requires at least 50 closed Demo trades across 30 calendar days,
net profit factor of at least 1.15, drawdown below 5%, no unresolved critical
drift, matched ledger and checksums, symbol/regime/time stability, an outcome
sample manifest, a rollback target, and complete code/data/model lineage.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_live_candidate_boundary.ps1
```

Current registry result: no Demo release has completed these hard gates, so the
report contains zero Live candidates and remains blocked. No evidence is
fabricated to create a package.

Key paths:

- `alphapilot/evolution/promotion/live_candidate.py`
- `alphapilot/reports/generate_live_candidate_boundary_report.py`
- `reports/live_candidate_boundary_report.json`
- `docs/V13.15.0-live-candidate-boundary.md`

Automatic Live promotion, live order execution, Withdraw API, credential
storage, and AI/Bandit/ML approval remain forbidden.

## V13.14.0 Automatic Demo Promotion

V13.14.0 adds a fail-closed bridge from immutable research evidence to OKX
Demo only. A candidate must pass point-in-time and leakage checks, at least
three walk-forward folds, FDR/Deflated-Sharpe/PBO checks, locked OOS and 2x cost
profit-factor gates, drawdown and concentration limits, frequency-specific OOS
samples, public-market Shadow samples, calendar coverage, and checksum checks.

Passed candidates create immutable `PromotionDecision` and `DemoRelease`
records. The exported Control Console contract contains the strategy, fixed
1000 USDT Demo risk envelope, evidence checksums, and release checksum. It never
contains credentials. Current registry data still has no formally eligible
candidate, so the readiness report correctly remains blocked rather than
fabricating a release.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_demo_promotion_readiness.ps1
```

Outputs:

- `reports/demo_promotion_readiness_report.json`
- `reports/demo_promotion_readiness_summary.md`
- `docs/V13.14.0-automatic-demo-promotion.md`

Demo releases may be automated in the separate Control Console. Live automatic
promotion, Withdraw API, and raw API key storage remain forbidden.

## V13.7.23 Paper Observation Quality Panel

V13.7.23 adds a report-only quality scoring model for the five V13.7.21 local
paper-observation tasks.

Generate the quality panel baseline:

```powershell
python -m alphapilot.reports.generate_v13_7_23_paper_observation_quality_panel
```

Outputs:

- `reports/v13_7_23_paper_observation_quality_panel_report.json`
- `reports/v13_7_23_paper_observation_quality_panel_summary.md`
- `docs/V13.7.23-paper-observation-quality-panel.md`

Result:

- taskCount: 5
- targetClosedSamplesTotal: 130
- qualityScoreMax: 100
- dryRunApproved: false
- liveTradingApproved: false

The desktop Control Console combines this scoring model with local observation
logs to show priority watch, continue observing, needs review, and pause
candidate states. V13.7.23 does not add Trade API, Withdraw API, API key
storage, real account reads, real position reads, order creation, exchange
Dry-run, live trading, or automation.

## V13.7.22 Paper Observation Logbook

V13.7.22 starts the local paper-observation journal for the five V13.7.21
task-pack candidates.

Generate the logbook baseline:

```powershell
python -m alphapilot.reports.generate_v13_7_22_paper_observation_logbook
```

Outputs:

- `reports/v13_7_22_paper_observation_logbook_report.json`
- `reports/v13_7_22_paper_observation_logbook_summary.md`
- `docs/V13.7.22-paper-observation-logbook.md`

Result:

- taskCount: 5
- targetClosedSamplesTotal: 130
- currentLogCount: 0
- dryRunApproved: false
- liveTradingApproved: false

This version only defines local daily observation fields and log types. The
desktop Control Console records the actual daily logs locally. V13.7.22 does not
add Trade API, Withdraw API, API key storage, real account reads, real position
reads, order creation, exchange Dry-run, live trading, or automation.

## Why Freqtrade

Freqtrade gives AlphaPilot a practical open-source base for:

- exchange data download
- strategy files
- local backtesting
- dry-run concepts
- structured user_data layout

V13.4 is not a strategy tuning version. It keeps the V13.3 strategy parameters fixed and focuses on the runtime path: data download, Freqtrade backtest, result JSON, and AlphaPilot report export.

## Structure

```text
user_data/                  Freqtrade user data folder
alphapilot/core/            proposal, workflow, lock, handbook skeletons
alphapilot/risk/            risk gate and position sizing skeletons
alphapilot/audit/           JSONL audit ledger skeleton
alphapilot/reports/         report schema and mock export
alphapilot/universe/        fixed Top 30 OKX USDT swap universe
scripts/                    safe PowerShell command wrappers
docs/                       V13.2/V13.3 docs and safety notes
```

## Setup

Install Docker Desktop before running Freqtrade commands.

Check local skeleton status:

```powershell
python -m alphapilot.scripts.print_project_status
python -m alphapilot.scripts.validate_config
```

Compile Python skeleton:

```powershell
python -m compileall alphapilot
```

## Freqtrade Commands

The scripts print commands by default. Use `-Run` only when you intentionally want to execute them.

Download public market data:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1
```

Run a local backtest command template:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_backtest.ps1
```

Export a mock AlphaPilot report:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/export_report.ps1
```

Safety scan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_safety.ps1
```

## V13.3 Volume Rebound V0.1

V13.3 implements the first AlphaPilot research strategy for baseline backtesting:

```text
AlphaPilot Volume Rebound V0.1
```

中文说明：

```text
V13.3 实现第一条 AlphaPilot 自研策略：放量反弹 V0.1。
本版本只用于研究和回测，不进行实盘交易，不接真实 API Key，不创建真实订单。
```

It does not trade live. It does not use real API keys. It is intended for research and backtesting only.

Core V0.1 rules:

- market: OKX USDT swap
- direction: long only
- timeframe: 15m
- fixed universe: Top 30 USDT swap pairs
- fixed stop loss: -3%
- take profit: +3%
- leverage: 5x research cap
- risk per trade: 1% documented research assumption
- fee rate: 0.05% one-way
- slippage rate: 0.05% one-way planned in reports, not yet applied by the Freqtrade command
- BTC crash filter: block new signals when BTC drops at least 1% over the latest three 15m candles
- 4h trend filter: current pair 4h close must be at least `EMA200 * 0.98`

Entry requires RSI14 between 30 and 55, volumeRatio at least 1.5, MACD histogram improvement, price near EMA20, and no chase above the Bollinger middle zone.

Backtest command preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_backtest.ps1 -Smoke -Timerange "20240101-20240701"
```

Download command preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" -Timeframes "15m,1h,4h" -Timerange "20240101-"
```

Add `-Run` only when Docker and Freqtrade are ready.

Report export:

```powershell
python -m alphapilot.reports.export_backtest_report
```

The exporter marks sample reports with `isMock=true`. It marks converted Freqtrade results with `isMock=false`.

The V13.3 strategy is not a live recommendation and not a production trading strategy.

## V13.4 Real Freqtrade Smoke Backtest

V13.4 completed the first real Freqtrade smoke backtest flow:

```text
public historical data download -> Freqtrade backtest -> Freqtrade JSON -> AlphaPilot report
```

The V13.4 smoke run used public OKX historical futures data only:

```text
Pairs: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
Timerange: 20260401-
Trades: 230
Win rate: 41.3043%
Total return: -15.542%
Max drawdown: 24.4939%
Profit factor: 0.8107
```

The versioned report is:

```text
reports/v13_4_smoke_backtest_report.json
```

It is a real converted Freqtrade result and contains:

```json
{
  "isMock": false
}
```

Runtime compatibility fixed in V13.4:

- `scripts/download_data.ps1` supports `-UseTop30`.
- `scripts/run_backtest.ps1` supports `-UseTop30`.
- Freqtrade 2026.6 config requires `entry_pricing` and `exit_pricing`; both are present in the backtest config and dry-run template.
- The report exporter supports the newer Freqtrade result layout where `.last_result.json` points to a zip file containing the real result JSON.
- Report export preserves missing real metrics as `null` and records `reportWarnings`.
- Real dynamic reports write `reports/latest_backtest_report.json` and `reports/smoke_backtest_report.json`; these are ignored so reruns do not pollute git status.
- Mock reports remain explicitly marked with `isMock=true`.

V13.4 is a process success, not a strategy approval. The current AlphaPilot Volume Rebound V0.1 smoke result is negative, with `profitFactor < 1`, negative total return, and high drawdown. It must not enter Dry-run. The next step is V13.4.1 Backtest Result Diagnosis.

## V13.4.1 Backtest Result Diagnosis

V13.4.1 diagnoses the first real smoke backtest result. It does not tune
strategy parameters, does not modify `AlphaPilotVolumeReboundV01.py`, and does
not enter Dry-run.

Run diagnosis:

```powershell
python -m alphapilot.reports.diagnose_backtest_result
```

Diagnosis outputs:

```text
reports/v13_4_1_diagnosis_report.json
reports/v13_4_1_diagnosis_summary.md
docs/V13.4.1-backtest-result-diagnosis.md
docs/v13_4_1_diagnosis_findings.md
```

Main findings from V13.4.1:

- The strategy cannot enter Dry-run.
- SOL contributed the largest pair-level loss: `-94.83085485 USDT`.
- April 2026 contributed the largest time-period loss: `-158.49408035 USDT`.
- `stop_loss` was the largest exit-reason loss: `-420.36251129 USDT`.
- `macd_histogram_two_candle_weakness` also lost heavily: `-345.28583144 USDT`.
- The weakest holding bucket was `1-3h`: `-120.76496941 USDT`.
- Fees were applied by Freqtrade and are material; slippage was not applied by the V13.4 command.
- Filter effectiveness is unavailable because V13.4 did not include skipped-signal instrumentation.

V13.4.1 prepares V0.2 candidate ideas, but those ideas are evidence categories,
not parameter changes. The next work should add signal audit instrumentation and
review the V0.2 candidates before any strategy modification.

## V13.4.2 Signal Audit Instrumentation

V13.4.2 adds skipped-signal audit instrumentation and filter effectiveness
tracking for AlphaPilot Volume Rebound V0.1.

This version does not tune strategy parameters, does not enter Dry-run, does not
call exchange private APIs, and does not create orders.

Run the audit:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_signal_audit.ps1
```

Outputs:

```text
reports/v13_4_2_signal_audit_report.json
reports/v13_4_2_signal_audit_summary.md
docs/V13.4.2-signal-audit-instrumentation.md
docs/filter-effectiveness-methodology.md
```

Current V13.4.2 smoke audit:

```text
Candles evaluated: 26496
Base candidate count: 26496
Final entry count: 305
Actual trade count: 230
Filter effectiveness available: true
Top skip reason: weak_4h_trend
Data missing count: 0
```

The largest primary blocks in the smoke sample are 4h trend, RSI, and volume
ratio. The least primary-blocking filter is the no-chase filter. These findings
prepare V13.4.3 strategy V0.2 candidate design, but V13.4.2 does not change the
V0.1 thresholds.

## V13.4.3 Strategy V0.2 Candidate Design

V13.4.3 creates evidence-based V0.2 strategy candidates from the V13.4.1
diagnosis and V13.4.2 signal audit. It does not tune parameters, does not run
Dry-run, does not change the V0.1 strategy, and prepares V13.4.4 comparative
backtesting.

V13.4.3 基于 V13.4.1 亏损诊断和 V13.4.2 信号审计，提出 V0.2 候选修改方向。本版本不调参、不进入
Dry-run、不修改 V0.1 真实策略，只为 V13.4.4 对比回测做准备。

Run candidate matrix generation:

```powershell
python -m alphapilot.reports.generate_v02_candidate_matrix
```

Outputs:

```text
reports/v13_4_3_v02_candidate_matrix.json
reports/v13_4_3_v02_candidate_summary.md
docs/V13.4.3-strategy-v02-candidate-design.md
docs/volume-rebound-v02-candidate-plan.md
```

V13.4.3 candidates:

```text
V0.2A Trend Strict Filter
V0.2B Volume Quality Filter
V0.2C Exit Cleanup
V0.2D Early Failure Exit
V0.2E Pair Risk Watchlist
```

All candidates are `candidate_only`. None are approved for Dry-run or live
trading.

## V13.4.4 V0.1 vs V0.2 Comparative Backtest

V13.4.4 compares V0.1 baseline with V0.2 candidate strategies using the same
smoke backtest scope. It does not enter Dry-run. It does not approve live
trading. It only identifies candidates for further validation.

V13.4.4 在同一 smoke 回测范围内比较 V0.1 baseline 与 V0.2 候选策略。本版本不进入 Dry-run，不批准实盘，只筛选值得进一步验证的候选。

Run comparative backtest:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_comparative_backtest.ps1 -Timerange "20260401-" -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" -Run
python -m alphapilot.reports.generate_comparative_backtest_report
```

Outputs:

```text
reports/v13_4_4_comparative_manifest.json
reports/v13_4_4_comparative_backtest_report.json
reports/v13_4_4_comparative_backtest_summary.md
docs/V13.4.4-comparative-backtest.md
docs/volume-rebound-v02-comparison-results.md
```

Result summary:

```text
V0.1 baseline: -15.542% return, 24.4939% drawdown, 0.8107 profit factor
V0.2A Trend Strict: -11.6607% return, 21.0664% drawdown, 0.8251 profit factor
V0.2B Volume Quality: -4.0845% return, 11.4841% drawdown, 0.9104 profit factor
V0.2C Exit Cleanup: -6.1609% return, 17.8594% drawdown, 0.9319 profit factor
V0.2D Early Failure Exit: -15.6258% return, 24.3002% drawdown, 0.7979 profit factor
V0.2E Pair Risk Watchlist: -10.3361% return, 17.93% drawdown, 0.8406 profit factor
```

A/B/C/E improved against the baseline comparison gate, while D did not. All
candidate returns are still negative, so `dryRunApproved=false`.

Smoke preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" -Timeframes "15m,1h,4h" -Timerange "20260401-"
powershell -ExecutionPolicy Bypass -File scripts/run_backtest.ps1 -Timerange "20260401-" -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT"
```

Add `-Run` only after Docker Desktop is installed and running.

## V13.4.5 Expanded Candidate Validation

V13.4.5 expands validation of the best V0.2 candidates on a larger Top30 scope
and adds slippage-adjusted metrics.

V13.4.5 对 V13.4.4 中相对较好的 B/C/E 候选进行 Top30 扩大验证，并加入滑点调整后的指标。
本版本不进入 Dry-run，不批准实盘。

Run expanded validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -UseTop30 -Timeframes "15m,1h,4h" -Timerange "20260101-" -Prepend -Run
powershell -ExecutionPolicy Bypass -File scripts/run_expanded_validation.ps1 -UseTop30 -Timerange "20260101-" -Run
python -m alphapilot.reports.generate_expanded_validation_report
```

Outputs:

```text
reports/v13_4_5_expanded_validation_manifest.json
reports/v13_4_5_expanded_validation_report.json
reports/v13_4_5_expanded_validation_summary.md
docs/V13.4.5-expanded-validation-slippage.md
docs/volume-rebound-expanded-validation-results.md
```

V13.4.5 result:

```text
Requested pairs: fixed Top30
Supported pairs: 28
Excluded pairs: TON/USDT:USDT, FET/USDT:USDT
Best raw candidate: AlphaPilotVolumeReboundV02CExitCleanup
Best slippage-adjusted candidate: AlphaPilotVolumeReboundV02CExitCleanup
dryRunApproved: false
```

All candidates remain negative after slippage post-processing. V02C is the best
relative candidate by profit factor, but it is not approved for Dry-run. The
next step should be V13.4.6 strategy direction review or V03 redesign.

## V13.4.6 Strategy Direction Review

V13.4.6 formally closes the current Volume Rebound V0.1/V0.2 research series
for Dry-run consideration and starts the V03 redesign stage.

中文说明：

```text
V13.4.6 基于 V13.4.5 扩大验证和滑点调整结果，正式复盘 Volume Rebound V0.1/V0.2 当前系列失败原因，并提出 V03 重设方向。
本版本不调参、不回测、不进入 Dry-run、不实盘。
```

Run the direction review:

```powershell
python -m alphapilot.reports.generate_strategy_direction_review
```

Outputs:

```text
reports/v13_4_6_strategy_direction_review.json
reports/v13_4_6_strategy_direction_summary.md
reports/v13_4_6_strategy_status_archive.json
docs/V13.4.6-strategy-direction-review.md
docs/volume-rebound-failure-review.md
docs/volume-rebound-v03-redesign-plan.md
```

V13.4.6 decision:

```text
strategyFamilyStatus = rejected_for_dry_run
dryRunApproved = false
```

Main conclusion:

- V0.1/V0.2 should not enter Dry-run.
- B/C/E are relative improvements only; expanded validation and slippage still reject them.
- The failure is not a single-parameter issue.
- V03 should redesign entry quality, trade frequency, reward/risk, trend structure, pair exposure, cost sensitivity, market regime, and signal confirmation.

V03 candidate directions:

- V03A Trend Pullback Continuation
- V03B Breakout Retest Confirmation
- V03C High Score Signal Only
- V03D 1h Main Timeframe

V03 quality gate before any Dry-run discussion:

- slippage-adjusted total return > 0
- slippage-adjusted profit factor > 1.15
- max drawdown materially below V0.1/V0.2 expanded validation
- no single pair dominates profit or loss
- smoke plus six-month Top30 validation must pass

V13.4.6 is research-only. It does not modify V0.1/V0.2 strategy code, does not
run backtests, does not enter Dry-run, does not use API keys, does not call
Trade API or Withdraw API, does not read accounts, does not create orders, and
does not auto trade.

## V13.4.7 V03 Candidate Selection

V13.4.7 selects Trend Pullback 1H as the first V03 implementation direction.
It does not implement strategy code, does not run backtests, and does not enter
Dry-run.

中文说明：

```text
V13.4.7 基于 V13.4.6 策略方向复盘，选择“1h 趋势回调延续”作为 V03 第一实现方向。
本版本只输出策略规格和 V13.4.8 实现计划，不写策略代码、不回测、不进入 Dry-run。
```

Selected V03 direction:

```text
selectedDirection = V03A+D
selectedStrategyId = alpha_trend_pullback_1h_v01
selectedStrategyName = AlphaPilot Trend Pullback 1H V0.1
status = spec_only
dryRunApproved = false
implementedStrategyCode = false
backtestExecuted = false
```

Outputs:

```text
alphapilot/strategy_specs/trend_pullback_1h_v01.py
alphapilot/reports/generate_v03_selection_report.py
reports/v13_4_7_v03_selection_report.json
reports/v13_4_7_v03_strategy_spec.md
docs/V13.4.7-v03-candidate-selection.md
docs/trend-pullback-1h-v01-spec.md
docs/v13_4_8_implementation_plan.md
```

V13.4.7 is research-only. It does not modify strategy execution files, does not
download data, does not run backtests, does not enter Dry-run, does not use API
keys, does not call Trade API or Withdraw API, does not read accounts, does not
create orders, and does not auto trade.

## V13.4.8 Trend Pullback 1H Smoke Backtest

V13.4.8 implements the V13.4.7 selected V03A+D direction as a real Freqtrade
strategy and runs a BTC/ETH/SOL smoke backtest.

中文说明：

```text
V13.4.8 实现 AlphaPilot Trend Pullback 1H V0.1，并完成 BTC / ETH / SOL 真实 Freqtrade 冒烟回测。
本版本仍然不进入 Dry-run，不实盘，不接 API Key，不自动交易。
```

Strategy:

```text
strategyClass = AlphaPilotTrendPullback1HV01
strategyId = alpha_trend_pullback_1h_v01
strategyName = AlphaPilot Trend Pullback 1H V0.1
timeframe = 1h
can_short = false
stoploss = -2.5%
minimal_roi = +5%
dryRunApproved = false
```

Smoke result:

```text
pairs = BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
timerange = 20260401-
isMock = false
tradeCount = 61
totalReturnPct = 6.6227
maxDrawdownPct = 9.8727
winRate = 47.541
profitFactor = 1.1933
```

Outputs:

```text
user_data/strategies/AlphaPilotTrendPullback1HV01.py
reports/v13_4_8_trend_pullback_1h_smoke_report.json
reports/v13_4_8_trend_pullback_1h_smoke_summary.md
docs/V13.4.8-trend-pullback-1h-smoke-backtest.md
docs/trend-pullback-1h-v01-implementation.md
```

V13.4.8 smoke success does not approve Dry-run. It is a research checkpoint only.

## V13.4.9 Trend Pullback Expanded Validation

V13.4.9 expands the V13.4.8 Trend Pullback 1H smoke result to a fixed Top30
validation scope and applies AlphaPilot slippage post-processing.

中文说明：

```text
V13.4.9 将 V13.4.8 的 BTC / ETH / SOL 冒烟结果扩大到固定 Top30 样本，并加入滑点后处理。
扩大验证失败，仍然不进入 Dry-run，不实盘，不接 API Key，不自动交易。
```

Run expanded validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -UseTop30 -Timeframes "1h,4h" -Timerange "20260101-" -Prepend -Run
powershell -ExecutionPolicy Bypass -File scripts/run_trend_pullback_expanded_validation.ps1 -UseTop30 -Timerange "20260101-" -Run
python -m alphapilot.reports.generate_trend_pullback_expanded_report
```

Result:

```text
requestedPairCount = 30
supportedPairs = 28
excludedPairs = TON/USDT:USDT, FET/USDT:USDT
isMock = false
dryRunApproved = false

rawTradeCount = 472
rawTotalReturnPct = -61.0503
rawMaxDrawdownPct = 67.296
rawWinRate = 31.5678
rawProfitFactor = 0.7067
rawMaxConsecutiveLosses = 13

slippageAdjustedTotalReturnPct = -113.218
slippageAdjustedProfitFactor = 0.5361
slippageAdjustedWinRate = 30.7203
slippageAdjustedMaxDrawdownPct = 112.2244
slippageCost = 521.67704423
```

Outputs:

```text
reports/v13_4_9_trend_pullback_expanded_manifest.json
reports/v13_4_9_trend_pullback_expanded_validation_report.json
reports/v13_4_9_trend_pullback_expanded_validation_summary.md
docs/V13.4.9-trend-pullback-expanded-validation.md
docs/trend-pullback-1h-expanded-results.md
```

V13.4.9 rejects Dry-run. The V13.4.8 smoke result did not generalize to the
wider Top30 validation sample. The next step should be V13.4.10 Trend Pullback
Redesign Review.

## V13.4.10 Trend Pullback Redesign Review

V13.4.10 reads the V13.4.8 smoke report and V13.4.9 expanded validation report
to explain why the small-sample Trend Pullback result failed to generalize.

中文说明：

```text
V13.4.10 只做失败复盘和重设评审。
本版本不调参、不修改策略代码、不下载数据、不运行回测、不进入 Dry-run、不实盘。
```

Run the review:

```powershell
python -m alphapilot.reports.generate_trend_pullback_redesign_review
```

Decision:

```text
strategyId = alpha_trend_pullback_1h_v01
currentStatus = needs_redesign
dryRunApproved = false
recommendedNextStep = V13.4.11 - Execution Reality and Liquidity Gate Design
```

Key conclusion:

```text
V13.4.8 BTC/ETH/SOL smoke:
tradeCount = 61
totalReturnPct = 6.6227
profitFactor = 1.1933
maxDrawdownPct = 9.8727

V13.4.9 Top30 raw:
tradeCount = 472
totalReturnPct = -61.0503
profitFactor = 0.7067
maxDrawdownPct = 67.296

V13.4.9 slippage-adjusted:
totalReturnPct = -113.218
profitFactor = 0.5361
maxDrawdownPct = 112.2244
```

Outputs:

```text
reports/v13_4_10_trend_pullback_redesign_review.json
reports/v13_4_10_trend_pullback_redesign_summary.md
docs/V13.4.10-trend-pullback-redesign-review.md
docs/trend-pullback-expanded-failure-analysis.md
docs/v13_4_11_next-step-options.md
```

V13.4.10 recommends redesigning the research gate around execution reality,
liquidity, market regime, pair universe, and signal quality before another
strategy implementation.

## V13.4.11 Execution Reality and Liquidity Gate Design

V13.4.11 adds the execution reality design layer required before any future
Dry-run candidate review. It does not tune strategy parameters, does not run a
backtest, does not enter Dry-run, and does not create real orders.

中文说明：

```text
V13.4.11 补上执行真实性测试层和流动性闸门。
本版本只做设计骨架和报告，不调参、不回测、不进入 Dry-run、不实盘。
```

Implemented modules:

```text
alphapilot/execution_reality/liquidity_gate.py
alphapilot/execution_reality/slippage_model.py
alphapilot/execution_reality/order_impact.py
alphapilot/execution_reality/shadow_trading_schema.py
alphapilot/execution_reality/live_feasibility_score.py
```

Generate the design report:

```powershell
python -m alphapilot.reports.generate_execution_reality_design_report
```

Outputs:

```text
reports/v13_4_11_execution_reality_design_report.json
reports/v13_4_11_execution_reality_summary.md
docs/V13.4.11-execution-reality-liquidity-gate.md
docs/liquidity-gate-design.md
docs/shadow-trading-design.md
docs/live-feasibility-score.md
```

V13.4.11 updates the proposal schema with optional execution reality context
fields and updates the risk gate so Dry-run candidate review requires liquidity,
execution reality, and shadow trading evidence first.

Safety boundary:

- No real API key.
- No Trade API.
- No Withdraw API.
- No real account reads.
- No real position reads.
- No real order creation.
- No automatic trading.
- No Dry-run execution.

V13.4.11 keeps `dryRunApproved=false` and `liveTradingApproved=false`.

## V13.4.12 Dynamic Universe and Regime Strategy Specification

V13.4.12 defines the new AlphaPilot strategy mainline:

```text
AlphaPilot Dynamic Regime Strategy V0.1
```

中文说明：

```text
V13.4.12 正式切换到动态币种池 + 市场状态路由 + 概率评分的新策略主线。
本版本只做规格，不写策略代码、不下载数据、不回测、不进入 Dry-run、不实盘。
```

New architecture:

```text
Universe -> Regime -> Module -> Probability -> Liquidity -> Risk -> Backtest / Shadow
```

V13.4.12 defines:

- `DynamicUniverseV01`
- historical dynamic universe snapshots
- `MarketRegimeRouterV01`
- `TrendContinuationModuleV01`
- `MeanReversionModuleV01`
- `ProbabilityScoreV01`
- liquidity gate integration
- risk gate integration
- the backtest validation plan

Generate the specification report:

```powershell
python -m alphapilot.reports.generate_dynamic_regime_strategy_spec
```

Outputs:

```text
reports/v13_4_12_dynamic_regime_strategy_spec.json
reports/v13_4_12_dynamic_regime_strategy_summary.md
docs/V13.4.12-dynamic-universe-regime-strategy-specification.md
docs/dynamic-universe-design.md
docs/market-regime-router-design.md
docs/probability-score-design.md
```

V13.4.12 keeps `dryRunApproved=false` and `liveTradingApproved=false`. The next
recommended step is V13.4.13 Historical Dynamic Universe Builder.

## V13.4.13 Historical Dynamic Universe Builder

V13.4.13 implements the historical Dynamic Universe builder needed by the new
Dynamic Regime strategy mainline.

中文说明：

```text
V13.4.13 基于本地公开历史 OHLCV，为每个历史日期生成当时可见的动态币种池快照。
本版本不写策略代码、不下载数据、不运行回测、不进入 Dry-run、不实盘。
```

Run the builder:

```powershell
python -m alphapilot.universe.build_historical_dynamic_universe
```

or:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_dynamic_universe.ps1 -Timerange "20260101-" -RefreshFrequency "daily" -MaxPairs 10
```

Outputs:

```text
reports/v13_4_13_dynamic_universe_snapshots.json
reports/v13_4_13_dynamic_universe_sample_snapshots.json
reports/v13_4_13_dynamic_universe_build_report.json
reports/v13_4_13_dynamic_universe_summary.md
docs/V13.4.13-historical-dynamic-universe-builder.md
docs/historical-dynamic-universe-builder.md
docs/dynamic-universe-lookahead-bias-protection.md
```

Lookahead bias rule:

```text
Each snapshot uses only candles with date < snapshotDate 00:00 UTC.
```

V13.4.13 reads local public OHLCV files only. It does not run a strategy
backtest, enter Dry-run, use API keys, call Trade API or Withdraw API, read
accounts, read positions, create orders, or auto trade.

## V13.4.14 Probability Score Dataset and Label Builder

V13.4.14 builds the statistical probability layer needed by the Dynamic Regime
strategy mainline. It reads V13.4.13 historical universe snapshots and local
public OHLCV, then creates point-in-time candidate samples, forward TP/SL
labels, MFE/MAE metrics, and a probability score table.

中文说明：

```text
V13.4.14 基于历史动态币种池和本地公开 OHLCV，构建概率评分样本、未来标签和条件概率表。
本版本只做统计数据集和标签，不写策略代码、不运行回测、不进入 Dry-run、不实盘。
```

Run the builder:

```powershell
python -m alphapilot.probability.build_probability_dataset
```

or:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_probability_dataset.ps1
```

Outputs:

```text
reports/v13_4_14_probability_dataset_report.json
reports/v13_4_14_probability_score_table.json
reports/v13_4_14_probability_sample_dataset.json
reports/v13_4_14_probability_dataset_summary.md
docs/V13.4.14-probability-score-dataset-label-builder.md
docs/probability-score-methodology.md
docs/probability-label-definition.md
```

No-lookahead rule:

```text
Features are point-in-time. Forward labels are evaluation-only and never flow back into feature buckets.
```

V13.4.14 produced 1,540 labeled samples across 155 historical snapshots. Most
bucket combinations are marked `insufficient_sample`, which keeps the decision
policy conservative and `observe_only`. V13.4.14 does not run a backtest, enter
Dry-run, use API keys, call Trade API or Withdraw API, read accounts, read
positions, create orders, or auto trade.

## V13.4.15 Dynamic Regime Strategy V0.1 Implementation

V13.4.15 implements the first Freqtrade strategy file for the Dynamic Regime
mainline:

```text
user_data/strategies/AlphaPilotDynamicRegimeV01.py
```

中文说明：

```text
V13.4.15 实现 AlphaPilot Dynamic Regime Strategy V0.1 的第一版策略代码。
本版本只写策略代码和文档，不运行回测、不进入 Dry-run、不实盘。
```

The strategy includes:

- Dynamic Universe filter from `reports/v13_4_13_dynamic_universe_snapshots.json`.
- Market Regime Router with `trend`, `mean_reversion`, and `avoid`.
- TrendContinuationModuleV01.
- MeanReversionModuleV01.
- ProbabilityScoreV01 lookup from `reports/v13_4_14_probability_score_table.json`.
- LiquidityGateV01 audit fallback for backtest research only.
- Audit columns prefixed with `ap_dyn_audit_`.

Static validation:

```powershell
python -m py_compile user_data\strategies\AlphaPilotDynamicRegimeV01.py
python -m compileall alphapilot
python -m alphapilot.scripts.validate_config
powershell -ExecutionPolicy Bypass -File scripts\check_safety.ps1
```

V13.4.15 does not run Freqtrade backtests, enter Dry-run, use API keys, call
Trade API or Withdraw API, read accounts, read positions, create orders, or
auto trade.

## V13.4.16 Dynamic Regime Strategy Smoke Backtest

V13.4.16 runs the first real smoke backtest for `AlphaPilotDynamicRegimeV01`.
It validates that Docker/Freqtrade can load the strategy, read the dynamic
universe and probability score table, and produce a real Freqtrade result.

中文说明：

```text
V13.4.16 对 AlphaPilotDynamicRegimeV01 执行 BTC / ETH / SOL 的真实本地 smoke backtest。
本版本不进入 Dry-run，不实盘，不接真实 API Key，不自动交易。
```

Run commands:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_data.ps1 -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" -Timeframes "1h,4h" -Timerange "20260401-" -Run
powershell -ExecutionPolicy Bypass -File scripts\run_dynamic_regime_smoke_backtest.ps1 -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" -Timerange "20260401-" -Timeframe "1h" -Run
python -m alphapilot.reports.generate_dynamic_regime_smoke_report
```

Outputs:

```text
reports/v13_4_16_dynamic_regime_smoke_report.json
reports/v13_4_16_dynamic_regime_smoke_summary.md
docs/V13.4.16-dynamic-regime-smoke-backtest.md
```

Smoke result:

```text
isMock: false
tradeCount: 0
totalReturnPct: 0.0
maxDrawdownPct: 0.0
probabilityScorePass: 0
finalEntrySignals: 0
```

The zero-trade result is expected from the current strict probability score
gate: V13.4.14 produced no `research_candidate` buckets for the smoke context.
The strategy runtime path is valid, but the probability gate blocks entries.
V13.4.16 keeps `dryRunApproved=false` and `liveTradingApproved=false`.

## V13.4.17 Dynamic Regime Expanded Validation

V13.4.17 expands `AlphaPilotDynamicRegimeV01` validation from the BTC / ETH /
SOL smoke scope to the historical dynamic universe.

Scope:

```text
strategy: AlphaPilotDynamicRegimeV01
timeframe: 1h
timerange: 20260101-
universe: historical dynamic universe selectedPairs union
slippage stress: 0.05%, 0.10%, 0.20%, 0.30% one-way
```

Run expanded validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_dynamic_regime_expanded_validation.ps1 -Timerange "20260101-" -Run
python -m alphapilot.reports.generate_dynamic_regime_expanded_report
```

Outputs:

```text
reports/v13_4_17_dynamic_regime_expanded_report.json
reports/v13_4_17_dynamic_regime_expanded_summary.md
docs/V13.4.17-dynamic-regime-expanded-validation.md
```

V13.4.17 reports raw metrics, slippage-adjusted metrics, liquidity gate
summary, probability score summary, probability bucket performance, and
regime/module breakdown. It keeps `dryRunApproved=false` and
`liveTradingApproved=false` regardless of research gate outcome.

Expanded validation result:

```text
isMock: false
pairCount: 27
tradeCount: 0
probabilityScorePass: 0
finalEntrySignals: 0
qualityGatePassed: false
```

Interpretation: the expanded runtime path works, but the V13.4.14 probability
gate still blocks all entries. This is not a strategy approval and not a
Dry-run candidate.

## V13.4.18 Dynamic Regime Pipeline Diagnosis

V13.4.18 diagnoses the zero-trade V13.4.17 result without running a new
backtest and without changing strategy rules, probability thresholds, bucket
tables, regime router logic, module rules, liquidity logic, Dry-run settings,
API keys, account access, order creation, or auto-trading behavior.

Run diagnosis:

```powershell
python -m alphapilot.reports.generate_dynamic_regime_signal_pipeline_diagnosis
```

Outputs:

```text
reports/v13_4_18_dynamic_regime_pipeline_diagnosis_report.json
reports/v13_4_18_dynamic_regime_pipeline_diagnosis_summary.md
docs/V13.4.18-dynamic-regime-pipeline-diagnosis.md
docs/probability-gate-coverage-diagnosis.md
docs/bucket-key-consistency-check.md
```

Diagnosis result:

```text
rowsEvaluated: 119679
trendModuleCandidates: 598
meanReversionModuleCandidates: 1775
probabilityLookupHits: 62352
probabilityScorePass: 0
finalEntrySignals: 0
researchCandidateBuckets: 0
currentGatePassBuckets: 0
bucketKeyMismatchSuspected: false
```

Interpretation: the signal pipeline reaches module candidate generation, but
the probability layer has no current-gate pass buckets. Bucket key format
appears consistent, so the likely V13.4.19 direction is probability bucket
coarsening and sample coverage expansion, not strategy approval.

## V13.4.19 Probability Bucket Coarsening

V13.4.19 reads the existing V13.4.14 probability score table and V13.4.18
pipeline diagnosis, then generates research-only coarsened bucket tables. It
does not modify `AlphaPilotDynamicRegimeV01.py`, does not modify the original
probability score table, does not loosen the current gate, does not run a
backtest, does not enter Dry-run, and does not approve live trading.

Run coarsening analysis:

```powershell
python -m alphapilot.reports.generate_probability_bucket_coarsening_report
```

Outputs:

```text
reports/v13_4_19_probability_bucket_coarsening_report.json
reports/v13_4_19_probability_bucket_coarsening_summary.md
reports/v13_4_19_probability_score_table_coarse_a.json
reports/v13_4_19_probability_score_table_coarse_b.json
reports/v13_4_19_probability_score_table_coarse_c.json
reports/v13_4_19_probability_score_table_coarse_d.json
docs/V13.4.19-probability-bucket-coarsening.md
docs/probability-bucket-coverage-expansion.md
docs/probability-gate-research-vs-trading.md
```

Result summary:

```text
original currentGatePassBucketCount: 0
original researchGatePassBucketCount: 0
original exploratoryGatePassBucketCount: 2
coarse_a researchGatePassBucketCount: 0
coarse_b researchGatePassBucketCount: 0
coarse_c researchGatePassBucketCount: 2
coarse_d researchGatePassBucketCount: 2
rootCauseConclusion: A. probability_table_too_sparse
recommendedNextStep: V13.4.20 - Probability Gate Candidate Wiring and Backtest Plan
```

Important limitation: the full raw probability sample dataset is not committed,
so V13.4.19 aggregates the existing bucket-level score table. Profit factor in
the coarsened tables is a sample-count weighted bucket-level approximation, not
a raw win/loss recomputation.

The current gate still has zero pass buckets after coarsening. Coarse C/D only
create research buckets, so they are candidates for a future backtest plan, not
Dry-run or live-trading approval.

## V13.4.20 Alpha Factor Research Layer

V13.4.20 changes the next step after V13.4.19. Instead of wiring coarse
probability buckets into strategy entry logic, it designs AlphaPilot's own Alpha
Factor Research Layer and Benchmark Strategy Suite.

中文说明：V13.4.20 基于 alpha101 的因子研究思路和 CryptoAgentPro.beta 的策略 / 市场状态参考，设计 AlphaPilot 自己的因子研究层和基准策略组。本版本不写交易策略、不回测、不进入 Dry-run、不接真实 API Key。

Why this route changed:

```text
V13.4.19 found coarse C / D research buckets, but the full raw sample dataset
is not committed and coarse profit factor is a bucket-level approximation.
Those buckets should not be promoted directly into strategy entries.
```

Generate the design report:

```powershell
python -m alphapilot.reports.generate_alpha_factor_research_design
```

Outputs:

```text
reports/v13_4_20_alpha_factor_research_design.json
reports/v13_4_20_alpha_factor_research_summary.md
docs/V13.4.20-alpha-factor-research-layer.md
docs/factor-data-panel-design.md
docs/factor-operator-subset.md
docs/benchmark-strategy-suite.md
docs/strategy-research-factory.md
```

The design includes:

```text
FactorDataPanel schema
Factor operator subset
Manual Factor Library V01
Factor Evaluation Metrics
Benchmark Strategy Suite
Strategy Research Factory
Dynamic Universe / Regime Router integration boundary
```

V13.4.20 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no strategy implementation
no backtest execution
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.21 FactorDataPanel and Manual Factor Library

V13.4.21 implements the local research data layer designed in V13.4.20. It
reads local public Freqtrade OHLCV files, builds a point-in-time
FactorDataPanel sample, and computes the first Manual Factor Library V01.

Run the builder:

```powershell
python -m alphapilot.factors.build_factor_data_panel
```

or:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_factor_panel.ps1
```

Default scope:

```text
timerange = 20260101-
timeframe = 1h
pairs = auto-discovered local OKX USDT swap futures pairs
```

Outputs:

```text
reports/v13_4_21_factor_panel_report.json
reports/v13_4_21_factor_panel_summary.md
reports/v13_4_21_factor_panel_sample.json
reports/v13_4_21_manual_factor_library_report.json
docs/V13.4.21-factor-data-panel-implementation.md
docs/factor-data-panel-local-data-generation.md
docs/manual-factor-library-v01.md
docs/no-lookahead-factor-computation.md
```

The initial local V13.4.21 build generated:

```text
rowsGenerated = 124111
loadedPairs = 28
factorCount = 16
averageCoveragePct = 99.8435
```

Estimated fields are explicit:

```text
quoteVolume = close * volume
quoteVolumeEstimated = true
vwap = (high + low + close) / 3
vwapEstimated = true
```

V13.4.21 no-lookahead rules:

- rolling factors use only current and historical rows
- cross-sectional ranks are computed only within the same timestamp
- BTC relative strength context is timestamp-aligned
- forward labels and backtest outcomes do not enter factor values
- missing data remains null rather than being fabricated

V13.4.21 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no backtest execution
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.22 Factor Evaluation Report and Forward Label Analysis

V13.4.22 evaluates the V13.4.21 Manual Factor Library against forward-looking
research labels. It rebuilds the full local FactorDataPanel from public OHLCV,
adds 4 / 8 / 12 / 24 bar forward returns, MFE / MAE, and TP/SL first-touch
labels, then evaluates all 16 manual factors.

Run the evaluator:

```powershell
python -m alphapilot.factors.evaluate_factors
```

or:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\evaluate_factors.ps1
```

Default scope:

```text
timerange = 20260101-
timeframe = 1h
horizons = 4,8,12,24
TP = +5%
SL = -2.5%
quantiles = 5
```

Outputs:

```text
reports/v13_4_22_factor_evaluation_report.json
reports/v13_4_22_factor_evaluation_summary.md
reports/v13_4_22_factor_candidates.json
docs/V13.4.22-factor-evaluation-report.md
docs/factor-evaluation-methodology.md
docs/no-lookahead-forward-labels.md
docs/research-factor-vs-trading-signal.md
```

The initial V13.4.22 local evaluation generated:

```text
sampleCount = 124111
validLabelCount = 123439
evaluatedFactorCount = 16
candidateFactors = 0
```

Top research observations:

```text
Top absolute RankIC: volatility_3d, atr_pct, volatility_24h
Top Q5-Q1 spread: trend_strength, distance_to_ema50, volume_expansion_3d
Top profit factor: trend_strength, distance_to_ema50, atr_pct
```

No factor passed the V13.4.22 candidate gate. This is a research result, not a
failure of the pipeline. It means the current manual factors should not be
promoted directly into strategy entries or Dry-run candidates.

V13.4.22 no-lookahead rules:

- features are point-in-time
- labels are forward-looking for evaluation only
- labels never alter factor values, sample selection, or universe membership
- candidate factors are research artifacts, not trade signals

V13.4.22 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no strategy implementation
no backtest execution
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.23 Benchmark Strategy Suite

V13.4.23 implements the benchmark suite designed in V13.4.20 and runs it as a
local research baseline against public historical OHLCV.

Run the benchmark suite:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_benchmark_suite.ps1 -UseTop10 -Timerange "20260101-" -Run
python -m alphapilot.reports.generate_benchmark_suite_report
```

Implemented benchmarks:

```text
BenchmarkNoTrade
BenchmarkBuyHoldBTC
BenchmarkEMATrend
BenchmarkRSIMeanReversion
BenchmarkMACDVolume
BenchmarkBollingerRebound
BenchmarkTD9Exhaustion
```

Outputs:

```text
reports/v13_4_23_benchmark_manifest.json
reports/v13_4_23_benchmark_suite_report.json
reports/v13_4_23_benchmark_suite_summary.md
docs/V13.4.23-benchmark-strategy-suite.md
docs/benchmark-strategy-definitions.md
docs/benchmark-results-interpretation.md
```

The report compares each benchmark to:

```text
NoTrade baseline
BuyHoldBTC baseline
```

It also estimates one-way slippage stress at 0.05%, 0.10%, and 0.20% in
post-processing. Freqtrade itself does not apply that slippage in this version.

V13.4.23 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no Dry-run approval
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
benchmark results are not trading signals
```

## V13.4.24 Benchmark Result Review and Strategy Research Reset

V13.4.24 reviews the V13.4.23 benchmark suite output. It does not modify
benchmark strategy code and does not run a new backtest.

Generate the review:

```powershell
python -m alphapilot.reports.generate_benchmark_result_review
```

Outputs:

```text
reports/v13_4_24_benchmark_result_review.json
reports/v13_4_24_benchmark_result_summary.md
reports/v13_4_24_benchmark_status_archive.json
docs/V13.4.24-benchmark-result-review.md
docs/benchmark-failure-analysis.md
docs/no-trade-buyhold-baseline-importance.md
docs/strategy-research-reset-plan.md
```

Initial review conclusions:

```text
0/5 active benchmarks beat NoTrade
0/5 active benchmarks beat BuyHoldBTC
BenchmarkBollingerRebound is relative best but not usable
relative best != tradable
recommended next step: Strategy Research Factory / Factor Hypothesis Mining
```

V13.4.24 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no new backtest run
no benchmark strategy code changes
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.25 Strategy Research Factory

V13.4.25 converts prior research evidence into a structured hypothesis registry.
It reads the V13.4.22 factor evaluation report, V13.4.23 benchmark suite report,
and V13.4.24 benchmark result review.

Generate the factory report:

```powershell
python -m alphapilot.reports.generate_strategy_research_factory_report
```

Outputs:

```text
reports/v13_4_25_strategy_research_factory_report.json
reports/v13_4_25_strategy_research_factory_summary.md
reports/v13_4_25_research_hypotheses.json
docs/V13.4.25-strategy-research-factory.md
docs/factor-hypothesis-mining.md
docs/rejected-strategy-hypotheses.md
docs/next-experiment-plan.md
```

Hypothesis counts:

```text
total hypotheses: 14
research-only: 9
deferred: 1
rejected: 4
high priority: HYP-001, HYP-002, HYP-004, HYP-006, HYP-007, HYP-008
```

V13.4.25 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no strategy implementation
no backtest execution
no Dry-run
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.26 Factor Hypothesis Validation Dataset

V13.4.26 validates the high-priority research hypotheses from V13.4.25 against
a rebuilt full FactorDataPanel and forward labels.

Run the validator:

```powershell
python -m alphapilot.research_factory.validate_hypotheses
```

PowerShell wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\validate_hypotheses.ps1
```

Outputs:

```text
reports/v13_4_26_hypothesis_validation_report.json
reports/v13_4_26_hypothesis_validation_summary.md
reports/v13_4_26_hypothesis_validation_dataset_sample.json
reports/v13_4_26_hypothesis_recommendations.json
docs/V13.4.26-hypothesis-validation-dataset.md
docs/hypothesis-validation-methodology.md
docs/no-lookahead-hypothesis-validation.md
docs/hypothesis-support-vs-trading-approval.md
```

Validation result:

```text
sampleCount: 124111
validatedHypothesisCount: 6
topSupportedHypotheses: none
unsupportedHypotheses: HYP-001, HYP-002, HYP-004, HYP-006, HYP-007, HYP-008
hypothesesWithPositiveExcessVsBTC: HYP-002
nextStep: V13.4.27 - Research Direction Reset / Data Expansion
```

V13.4.26 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no strategy implementation
no backtest execution
no Dry-run
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.27 Market Regime and Data Integrity Review

V13.4.27 pauses the previous data expansion plan and first validates local
OHLCV integrity plus market regime context.

Run the review:

```powershell
python -m alphapilot.reports.generate_market_regime_data_integrity_review
```

Outputs:

```text
reports/v13_4_27_market_regime_data_integrity_report.json
reports/v13_4_27_market_regime_data_integrity_summary.md
reports/v13_4_27_btc_regime_labels.json
reports/v13_4_27_data_quality_by_pair.json
docs/V13.4.27-market-regime-data-integrity-review.md
docs/ohlcv-data-integrity-checks.md
docs/market-regime-labeling-methodology.md
docs/regime-aware-research-recommendation.md
```

Initial local result:

```text
status: completed_with_warnings
dataIntegrity.status: warning
pairCount: 30
pairTimeframeCount: 60
validCount: 55
warningCount: 1
invalidCount: 0
missingFileCount: 4
totalInvalidOhlcRows: 0
totalDuplicateTimestamps: 0
```

The review found no obvious OHLC corruption in the checked local files, but it
did find local coverage warnings and a strongly regime-sensitive BTC sample.
Recent long-only technical research failures should therefore be interpreted as
a combination of adverse bear/high-volatility context plus sparse validated
alpha, not as a single simple parameter issue.

V13.4.27 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no strategy implementation
no backtest execution
no data download
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.28 Market Data Coverage Repair and Public Data Expansion

V13.4.28 attempts to repair the V13.4.27 local OHLCV coverage warnings before
adding new market-context schemas. It also adds a public-data expansion
skeleton for Funding Rate, Open Interest, Orderbook Spread Proxy, Liquidation,
and Market Regime Proxy inputs.

Run the post-repair integrity review:

```powershell
python -m alphapilot.reports.generate_market_regime_data_integrity_review --output-report reports/v13_4_28_post_repair_market_regime_data_integrity_report.json --output-summary reports/v13_4_28_post_repair_market_regime_data_integrity_summary.md --output-btc-labels reports/v13_4_28_post_repair_btc_regime_labels.json --output-data-quality reports/v13_4_28_post_repair_data_quality_by_pair.json
```

Generate the V13.4.28 coverage and expansion reports:

```powershell
python -m alphapilot.reports.generate_market_data_expansion_report
```

Outputs:

```text
reports/v13_4_28_data_coverage_repair_report.json
reports/v13_4_28_data_coverage_repair_summary.md
reports/v13_4_28_post_repair_data_quality_by_pair.json
reports/v13_4_28_market_data_expansion_report.json
reports/v13_4_28_market_data_expansion_summary.md
docs/V13.4.28-market-data-coverage-repair-expansion.md
docs/funding-rate-data-design.md
docs/open-interest-data-design.md
docs/orderbook-spread-proxy-design.md
docs/market-data-source-registry.md
docs/data-quality-requirements.md
```

Current V13.4.28 result:

```text
status: completed_with_unresolved_gaps
preRepairMissingFileCount: 4
postRepairMissingFileCount: 4
unresolved files: FET/USDT:USDT 1h/4h, TON/USDT:USDT 1h/4h
remaining warning: ORDI/USDT:USDT 4h extreme close-to-close return review
```

The public data expansion is schema-only in V13.4.28. No funding, open
interest, orderbook, liquidation, or ticker collector is active yet. The data
source registry records public-only sources and keeps `requiresApiKey=false`
and `usesPrivateEndpoint=false`.

V13.4.28 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no strategy implementation
no backtest execution
no Dry-run
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.29 Short Rejection 1H Research Strategy

V13.4.29 adds a simple short-only 1h research strategy:

```text
AlphaPilot Short Rejection 1H V0.1
```

The strategy tests whether a rebound-failure short idea has research value in
the current local public OKX futures data. It does not treat bear regime as a
hard entry gate. It uses a small `shortScore` model and only a few hard
blockers.

Run smoke backtest:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_short_rejection_backtest.ps1 -Smoke -Run
```

Run expanded supported-pair backtest:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_short_rejection_backtest.ps1 -Expanded -UseSupportedPairs -Timerange "20260101-" -Run
```

Generate the report:

```powershell
python -m alphapilot.reports.generate_short_rejection_report
```

Outputs:

```text
reports/v13_4_29_short_rejection_1h_report.json
reports/v13_4_29_short_rejection_1h_summary.md
docs/V13.4.29-short-rejection-1h-research-strategy.md
docs/short-rejection-1h-strategy-rules.md
docs/short-strategy-risk-notes.md
```

Current result:

```text
smoke: 828 short trades, totalReturnPct -80.8628, profitFactor 0.6457
expanded: 5052 short trades, totalReturnPct -99.9966, profitFactor 0.782
expanded slippageAdjustedTotalReturnPct: -217.1225
expanded slippageAdjustedProfitFactor: 0.5966
maxDrawdownPct: 99.9966
researchWorthContinuing: false
```

Scope decisions:

```text
excludedPairs: FET/USDT:USDT, TON/USDT:USDT
watchlistPairs: ORDI/USDT:USDT
```

V13.4.29 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no Dry-run
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.30 Short Rejection Failure Review

V13.4.30 reviews the failed V13.4.29 short-only research strategy and archives it as:

```text
failed_research_current_sample
```

中文说明：

```text
V13.4.30 复盘 V13.4.29 做空研究策略失败结果，归档该策略为 failed_research_current_sample，并提炼后续做空研究的负样本规则。
本版本不调参、不回测、不进入 Dry-run、不接真实 API Key。
```

The source evidence is:

```text
reports/v13_4_29_short_rejection_1h_report.json
reports/v13_4_29_short_rejection_1h_summary.md
```

Generate the failure review:

```powershell
python -m alphapilot.reports.generate_short_rejection_failure_review
```

Outputs:

```text
reports/v13_4_30_short_rejection_failure_review.json
reports/v13_4_30_short_rejection_failure_summary.md
reports/v13_4_30_short_strategy_status_archive.json
reports/v13_4_30_negative_research_rules.json
docs/V13.4.30-short-rejection-failure-review.md
docs/short-strategy-negative-research-rules.md
docs/failed-strategy-archive-policy.md
docs/future-short-research-recommendations.md
```

Current conclusion:

```text
researchWorthContinuing: false
dryRunApproved: false
liveTradingApproved: false
nextStepRecommendation: V13.4.31 - Low-Frequency Mainstream Coin Research Plan
```

V13.4.30 remains report-only:

```text
no strategy modification
no new backtest
no Dry-run
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.31 Low-Frequency Mainstream Coin Research Plan

V13.4.31 narrows the next research track to BTC/ETH/SOL on 4h/1d timeframes.

中文说明：

```text
V13.4.31 将研究范围收窄到 BTC/ETH/SOL 的 4h/1d 低频方向，设计 long/short 均可研究的 regime-aware 低频研究计划。
本版本不写策略、不回测、不进入 Dry-run、不接 API Key。
```

Generate the research plan:

```powershell
python -m alphapilot.reports.generate_low_frequency_research_plan
```

Outputs:

```text
reports/v13_4_31_low_frequency_research_plan.json
reports/v13_4_31_low_frequency_research_summary.md
docs/V13.4.31-low-frequency-mainstream-research-plan.md
docs/low-frequency-research-hypotheses.md
docs/mainstream-coin-research-scope.md
docs/regime-aware-long-short-research.md
```

Research scope:

```text
pairs: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
primaryTimeframes: 4h, 1d
optionalTimeframes: 1h
```

V13.4.31 defines five low-frequency research hypotheses:

```text
LF-HYP-001 BTC/ETH/SOL 4h Trend Following
LF-HYP-002 BTC/ETH/SOL 4h Bear Rejection Short
LF-HYP-003 1d Regime + 4h Entry
LF-HYP-004 Breakout Retest on Mainstream Coins
LF-HYP-005 NoTrade as Active Decision
```

Long and short can both be researched, but they must be evaluated separately.
Market regime is a direction-scoring and risk-weighting context, not the only
hard entry switch.

V13.4.31 remains research-plan-only:

```text
no strategy code
no data download
no backtest
no Dry-run
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.32 Low-Frequency Data Preparation and Baseline Builder

V13.4.32 prepares BTC/ETH/SOL 4h/1d public OHLCV data and builds report-only baseline references before any low-frequency strategy implementation.

中文说明：

```text
V13.4.32 只做低频数据准备和基线报告：
检查 BTC/ETH/SOL 的 4h/1d 本地公共 OHLCV 数据，
生成 NoTrade / BuyHold / EqualWeight 基线，
为后续低频策略研究建立最低比较标准。
```

Generate the reports:

```powershell
python -m alphapilot.reports.generate_low_frequency_baseline_report
```

Optional public OHLCV preparation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_low_frequency_baselines.ps1 -RunDownload -Prepend
```

Outputs:

```text
reports/v13_4_32_low_frequency_data_report.json
reports/v13_4_32_low_frequency_baseline_report.json
reports/v13_4_32_low_frequency_baseline_summary.md
docs/V13.4.32-low-frequency-data-baseline-builder.md
docs/low-frequency-data-quality-checks.md
docs/no-trade-buyhold-mainstream-baselines.md
docs/future-low-frequency-strategy-requirements.md
```

Baseline set:

```text
NoTrade
BuyHold BTC
BuyHold ETH
BuyHold SOL
EqualWeight BTC/ETH/SOL
```

V13.4.32 remains report-only:

```text
no strategy implementation
no Freqtrade strategy backtest
no Dry-run approval
no live trading approval
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.33 Low-Frequency Candidate Specification

V13.4.33 uses the V13.4.32 low-frequency baselines to define candidate strategy specs and baseline hurdles before any strategy code is written.

中文说明：

```text
V13.4.33 基于 V13.4.32 的低频基线，
设计 BTC/ETH/SOL 4h/1d 低频候选策略规格与 baseline hurdles。
本版本不写策略、不回测、不进入 Dry-run、不接 API Key。
```

Generate the candidate specification report:

```powershell
python -m alphapilot.reports.generate_low_frequency_candidate_spec_report
```

Outputs:

```text
reports/v13_4_33_low_frequency_candidate_spec_report.json
reports/v13_4_33_low_frequency_candidate_spec_summary.md
docs/V13.4.33-low-frequency-candidate-specification.md
docs/low-frequency-baseline-hurdles.md
docs/low-frequency-directional-score-framework.md
docs/v13_4_34_candidate-implementation-plan.md
```

Candidate specs:

```text
LF-CAND-A-4H-EMA-TREND-LONG
LF-CAND-B-4H-BEAR-REJECTION-SHORT
LF-CAND-C-1D-REGIME-4H-ENTRY-ROUTER
LF-CAND-D-4H-BREAKOUT-RETEST
LF-CAND-E-NOTRADE-DEFENSIVE-REGIME
```

V13.4.33 remains spec-only:

```text
no strategy implementation
no Freqtrade strategy backtest
no data download
no Dry-run approval
no live trading approval
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.34 Low-Frequency Directional 4H Research Strategy

V13.4.34 implements the first real low-frequency directional 4h research strategy and runs a local Freqtrade backtest for BTC/ETH/SOL.

中文说明：

```text
V13.4.34 实现 BTC/ETH/SOL 4h 多空低频研究策略，
执行真实本地 Freqtrade 回测，
并输出 baseline / slippage / regime / long-short 分解报告。
本版本结果为失败研究样本，不进入 Dry-run，不进入实盘。
```

Run the research backtest:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_low_frequency_directional_backtest.ps1 -Timerange "20240101-" -Run
python -m alphapilot.reports.generate_low_frequency_directional_report
```

Outputs:

```text
user_data/strategies/AlphaPilotLowFrequencyDirectional4HV01.py
user_data/backtest_results/v13_4_34_low_frequency_directional_4h.zip
reports/v13_4_34_low_frequency_directional_4h_report.json
reports/v13_4_34_low_frequency_directional_4h_summary.md
docs/V13.4.34-low-frequency-directional-4h-research-strategy.md
docs/low-frequency-directional-4h-strategy-rules.md
docs/low-frequency-directional-results-interpretation.md
```

Real backtest result:

```text
tradeCount: 2821
longTradeCount: 1312
shortTradeCount: 1509
totalReturnPct: -99.9659
slippageAdjustedTotalReturnPct: -150.0949
maxDrawdownPct: 99.9676
profitFactor: 0.6099
researchWorthContinuing: false
```

V13.4.34 remains research-only:

```text
no Dry-run approval
no live trading approval
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.35 Multi-Strategy Batch Research Backtest

V13.4.35 stops the single-strategy loop and tests eight low-frequency BTC/ETH/SOL 4h OHLCV-only strategy candidates in one research batch.

中文说明：

```text
V13.4.35 一次性实现 8 个低频 4h 研究策略，
批量运行真实本地 Freqtrade 回测，
统一生成 leaderboard / slippage / baseline 对比报告。
本轮所有策略均未通过研究继续门槛。
```

Run the batch:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_multi_strategy_batch_backtest.ps1 -UseMainstream -Timerange "20240101-" -Run
python -m alphapilot.reports.generate_multi_strategy_batch_report
```

Outputs:

```text
user_data/strategies/AlphaPilotLowFrequencyStrategyBatchV01.py
scripts/run_multi_strategy_batch_backtest.ps1
reports/v13_4_35_multi_strategy_batch_manifest.json
reports/v13_4_35_multi_strategy_batch_report.json
reports/v13_4_35_multi_strategy_batch_summary.md
docs/V13.4.35-multi-strategy-batch-backtest.md
docs/multi-strategy-batch-strategy-definitions.md
docs/multi-strategy-batch-results-interpretation.md
```

Batch result:

```text
realBacktestCount: 8
failedStrategies: 0
beatsNoTradeCount: 0
beatsEqualWeightCount: 0
researchWorthContinuingCount: 0
bestRawStrategy: AlphaPilotBatchH_VolatilityCompressionBreakout4H
bestRawReturnPct: -31.9496
bestSlippageAdjustedReturnPct: -49.6662
```

V13.4.35 remains research-only:

```text
no Dry-run approval
no live trading approval
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.5 Derivatives ML-Gated Strategy Pipeline

V13.5 pivots away from repeated OHLCV-only parameter tuning. It implements a
research-only derivatives feature panel, triple-barrier labeling, walk-forward
probability gate, and deterministic rule mining.

中文说明：

```text
V13.5 不再继续微调普通技术指标策略。
本版本建立衍生品特征 + 2R/1R 标签 + 概率门控 + 规则挖掘管线。
目标是把“胜率 > 55%、盈亏比接近 2:1”作为硬验收门槛。
未通过门槛，不进入模拟盘，不进入 Dry-run。
```

Run the V13.5 research pipeline:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_derivatives_ml_research.ps1 -Timeframe 4h -Run
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_derivatives_ml_research.ps1 -Timeframe 1h -Run
```

Outputs:

```text
alphapilot/derivatives/feature_panel.py
alphapilot/ml_gate/triple_barrier.py
alphapilot/ml_gate/probability_gate.py
alphapilot/reports/generate_v13_5_derivatives_ml_strategy_report.py
scripts/run_v13_5_derivatives_ml_research.ps1
reports/v13_5_derivatives_ml_strategy_4h_report.json
reports/v13_5_derivatives_ml_strategy_4h_summary.md
reports/v13_5_derivatives_ml_strategy_1h_report.json
reports/v13_5_derivatives_ml_strategy_1h_summary.md
docs/V13.5-derivatives-ml-gated-strategy-pipeline.md
docs/v13_5_strategy_decision_summary.md
```

Current decision:

```text
4h: no paper approval
1h: no paper approval
Dry-run: false
Live trading: false
Reason: no candidate passed the 55% win-rate and 2R hard gate
```

Closest findings:

```text
4h: ETH long continuation + neutral mark basis was historically useful but
failed on sample size, reward/risk, and recent robustness.

1h: SOL long continuation + low ATR had enough trades and win rate above 55%,
but failed on reward/risk and drawdown.
```

V13.5 remains research-only:

```text
no Dry-run approval
no live trading approval
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.5.1 Expanded Relaxed Derivatives Research

V13.5.1 expands the V13.5 pipeline to the locally available 28-pair OKX futures
universe and adds a relaxed shadow-watchlist gate.

中文说明：

```text
V13.5.1 按用户要求扩大测试币种，并略微放宽研究门槛。
但放宽后的候选仍然只是 research / forward-confirmation，不等于模拟盘或实盘批准。
```

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_1_expanded_relaxed_research.ps1 -Timeframe 1h -Run
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_1_expanded_relaxed_research.ps1 -Timeframe 4h -Run
```

Outputs:

```text
alphapilot/ml_gate/research_gates.py
alphapilot/reports/generate_v13_5_1_expanded_relaxed_research_report.py
scripts/run_v13_5_1_expanded_relaxed_research.ps1
reports/v13_5_1_expanded_relaxed_1h_report.json
reports/v13_5_1_expanded_relaxed_1h_summary.md
reports/v13_5_1_expanded_relaxed_4h_report.json
reports/v13_5_1_expanded_relaxed_4h_summary.md
docs/V13.5.1-expanded-relaxed-derivatives-research.md
```

Current V13.5.1 result:

```text
Loaded pairs: 28
Probability hard gate approved: false
Probability relaxed shadow-watchlist approved: false
Deterministic forward-confirmation candidate found: true
Paper approved: false
Dry-run approved: false
Live trading approved: false
```

Closest 4h deterministic mined candidate:

```text
Condition: BTC regime bear + return_3 > 6% + Bollinger z > 2.0
Trades: 166
Win rate: 60.8434%
Reward/risk: 1.9922
Profit factor: 3.0956
Max drawdown: 35.4801%
Holdout trades: 50
Holdout win rate: 56.0%
Holdout reward/risk: 1.9965
Holdout profit factor: 2.5411
Status: forward-confirmation only, not paper approved
```

Closest 1h deterministic mined candidate:

```text
Condition: short_reversal_candidate + BTC regime bull + relative_return_6 between -1% and 1%
Trades: 187
Win rate: 73.262%
Reward/risk: 1.2321
Profit factor: 3.3759
Max drawdown: 37.9023%
Holdout trades: 57
Holdout win rate: 70.1754%
Holdout reward/risk: 2.0235
Holdout profit factor: 4.7612
Status: forward-confirmation only, not paper approved
```

Interpretation:

```text
V13.5.1 found useful deterministic research candidates, but the probability-gated
walk-forward layer still did not pass. These candidates should be used for
forward-confirmation / shadow observation design, not paper or Dry-run execution.
```

## V13.5.2 Forward Confirmation and Local Paper Sandbox

V13.5.2 replays the V13.5.1 deterministic candidates as fixed rules and checks
their final holdout segment. This version introduces a local paper sandbox gate.

Important boundary:

```text
localPaperSandboxApproved = local simulated observation only
exchangeDryRunApproved = false
liveTradingApproved = false
```

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_2_forward_confirmation.ps1 -Run
```

Outputs:

```text
alphapilot/reports/generate_v13_5_2_forward_confirmation_report.py
scripts/run_v13_5_2_forward_confirmation.ps1
reports/v13_5_2_forward_confirmation_report.json
reports/v13_5_2_forward_confirmation_summary.md
reports/v13_5_2_forward_confirmation_signal_log.json
docs/V13.5.2-forward-confirmation-local-paper-sandbox.md
```

Current V13.5.2 decision:

```text
Local paper sandbox approved: true
Approved candidate: v13_5_1_1h_short_reversal_bull_relative_return
Exchange Dry-run approved: false
Live trading approved: false
```

Approved local paper candidate:

```text
Condition: short_reversal_candidate + BTC bull regime + relative_return_6 between -1% and 1%
Timeframe: 1h
Confirmation trades: 57
Confirmation win rate: 70.1754%
Confirmation reward/risk: 2.0235
Confirmation profit factor: 4.7612
Confirmation max drawdown: 11.9756%
```

Rejected candidate:

```text
4h BTC bear + return_3 > 6% + Bollinger z > 2.0
Reason: confirmation drawdown above 20%
```

V13.5.2 does not use API keys, does not call Trade API or Withdraw API, does
not read accounts or positions, does not create orders, and does not auto trade.

## V13.5.3 Local Paper Sandbox Ledger

V13.5.3 starts a local simulated ledger for the V13.5.2 approved candidate. It
uses local JSON signal logs only. It does not run Freqtrade exchange Dry-run,
does not connect to an exchange, does not use API keys, and does not create
orders.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_3_local_paper_sandbox.ps1 -Run
```

Outputs:

```text
alphapilot/paper_sandbox/local_paper_ledger.py
alphapilot/reports/generate_v13_5_3_local_paper_sandbox_report.py
scripts/run_v13_5_3_local_paper_sandbox.ps1
reports/v13_5_3_local_paper_sandbox_ledger.json
reports/v13_5_3_local_paper_sandbox_report.json
reports/v13_5_3_local_paper_sandbox_summary.md
docs/V13.5.3-local-paper-sandbox-ledger.md
```

Current V13.5.3 decision:

```text
Local paper sandbox started: true
Paper monitoring ready: true
Exchange Dry-run approved: false
Live trading approved: false
```

Default local paper ledger result:

```text
initialEquity: 10000
maxConcurrentPositions: 8
filledTrades: 41
winRate: 60.9756%
rewardRiskRatio: 1.6922
profitFactor: 2.644
totalReturnPct: 14.9788
maxDrawdownPct: 3.242758
```

The concurrency sensitivity table is included in the V13.5.3 summary. Lower
caps such as 3 and 5 positions were too restrictive for this clustered
multi-pair signal. `maxConcurrentPositions=8` is the first tested cap that
passes the local paper monitoring gate.

V13.5.3 remains local simulation only:

```text
no Trade API
no Withdraw API
no API key storage
no real account reads
no real position reads
no real orders
no automatic trading
exchange Dry-run remains disabled
```

## V13.5.4 Local Paper Monitoring and Fresh Evidence Refresh

V13.5.4 turns the V13.5.3 one-shot local paper ledger into a repeatable local
monitoring pipeline. It can optionally refresh public 1h market data, rerun the
V13.5.2 forward-confirmation signal log, rerun the V13.5.3 local paper ledger,
and generate a V13.5.4 monitoring report with rolling windows, freshness checks,
skipped-signal analysis, and decay warnings.

Important boundary:

```text
localPaperMonitoringActive = local simulated observation only
exchangeDryRunReviewReady = false
liveTradingApproved = false
```

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_4_local_paper_monitoring.ps1 -RefreshPublicData
```

Run with public data refresh:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_4_local_paper_monitoring.ps1 -RefreshPublicData -Run
```

Outputs:

```text
alphapilot/paper_sandbox/paper_monitoring.py
alphapilot/reports/generate_v13_5_4_local_paper_monitoring_report.py
scripts/run_v13_5_4_local_paper_monitoring.ps1
reports/v13_5_4_local_paper_monitoring_report.json
reports/v13_5_4_local_paper_monitoring_summary.md
reports/v13_5_4_local_paper_monitoring_events.json
docs/V13.5.4-local-paper-monitoring.md
```

Current V13.5.4 decision:

```text
Local paper monitoring active: true
Monitoring health: watch
Continue local paper monitoring: true
Exchange Dry-run review ready: false
Live trading approved: false
Reason: local_paper_monitoring_continues_with_decay_warnings
```

Full local paper ledger metrics:

```text
filledTrades: 41
winRate: 60.9756%
rewardRiskRatio: 1.6922
profitFactor: 2.644
totalReturnPct: 14.9788
maxDrawdownPct: 3.242758
maxConsecutiveLosses: 3
```

Recent-window warnings:

```text
last 10 trades: winRate=50.0%, rewardRisk=1.1522, profitFactor=1.1522
last 20 trades: winRate=50.0%, rewardRisk=1.3738, profitFactor=1.3738
closed fill freshness: stale
signal-to-closed-fill lag: above 5 days
some approved signals skipped by max concurrent position cap
```

V13.5.4 public data refresh extended the local 1h OKX futures data through
`2026-07-05 16:00 UTC` for the checked BTC/ETH/SOL files. The monitoring report
still does not approve exchange Dry-run because recent closed-fill evidence is
not fresh enough and the recent 10/20-trade windows show decay.

V13.5.4 remains local simulation only:

```text
no Trade API
no Withdraw API
no API key storage
no real account reads
no real position reads
no real orders
no automatic trading
exchange Dry-run remains disabled
```

## V13.5.5 Event Pool Expansion

V13.5.5 expands the amount of public historical data converted into candidate
events. It is an anti-overfit research checkpoint: broad sample coverage,
pair/month concentration, and recent holdout size are reported separately from
headline win-rate metrics.

Important boundary:

```text
eventPoolExpanded = public historical data research only
newLocalPaperCandidateApproved = false
exchangeDryRunApproved = false
liveTradingApproved = false
```

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_5_event_pool_expansion.ps1
```

Refresh public data and generate the event-pool report:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_5_event_pool_expansion.ps1 -RefreshPublicData -Prepend -Run
```

Generate from existing local data:

```powershell
python -m alphapilot.reports.generate_v13_5_5_event_pool_expansion_report
```

Outputs:

```text
alphapilot/reports/generate_v13_5_5_event_pool_expansion_report.py
scripts/run_v13_5_5_event_pool_expansion.ps1
reports/v13_5_5_event_pool_expansion_report.json
reports/v13_5_5_event_pool_expansion_summary.md
reports/v13_5_5_event_pool_candidates.json
docs/V13.5.5-event-pool-expansion.md
```

V13.5.5 does not optimize parameters to chase a target win rate. It lowers the
event-pool win-rate screen to `45%` while keeping the `2R` reward/risk target
unchanged. Profit factor, drawdown, total return, sample breadth, and holdout
checks still have to pass before any pool can become a forward-confirmation
candidate.

The default V13.5.5 report uses `1h` and `4h`. `15m` can be supplied manually,
but it is not the default because it is substantially heavier and more prone to
short-term noise.

V13.5.5 remains research-only:

```text
no Trade API
no Withdraw API
no API key storage
no real account reads
no real position reads
no real orders
no automatic trading
exchange Dry-run remains disabled
```

## V13.5.6 High Reward Event Redesign

V13.5.6 keeps the target at `2R` and redesigns event definitions toward
structures that can naturally support higher reward/risk. This is not a
parameter-optimization pass. It adds high-reward event hypotheses, labels them
with the existing triple-barrier simulator, and reports whether any pool has
enough breadth and recent stability to deserve forward confirmation.

Important boundary:

```text
targetRMultiple = 2.0
newLocalPaperCandidateApproved = report result only
exploratoryLocalPaperWatchApproved = report result only
exchangeDryRunApproved = false
liveTradingApproved = false
```

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_6_high_reward_event_redesign.ps1
```

Generate from existing local data:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_6_high_reward_event_redesign.ps1 -Run
```

Outputs:

```text
alphapilot/ml_gate/high_reward_event_setups.py
alphapilot/ml_gate/high_reward_triple_barrier.py
alphapilot/reports/generate_v13_5_6_high_reward_event_redesign_report.py
scripts/run_v13_5_6_high_reward_event_redesign.ps1
reports/v13_5_6_high_reward_event_redesign_report.json
reports/v13_5_6_high_reward_event_redesign_summary.md
reports/v13_5_6_high_reward_candidates.json
docs/V13.5.6-high-reward-event-redesign.md
```

V13.5.6 reports the cost-adjusted net reward/risk ceiling because roundtrip fee
and slippage reduce observed net winners and deepen observed net losses. This
is an accounting clarification, not a relaxation of the `2R` target.

If a fixed exploratory filter clears the local watch screen, it is only approved
for local paper observation. It is not approved for exchange Dry-run, live
trading, order creation, or automatic execution.

V13.5.6 remains research-only:

```text
no Trade API
no Withdraw API
no API key storage
no real account reads
no real position reads
no real orders
no automatic trading
exchange Dry-run remains disabled
```

## V13.5.7 External Alpha Overlay Research

V13.5.7 reviews two public GitHub projects as concept references and adds an
Alpha101-style factor overlay to the existing high-reward event research
pipeline.

External references:

```text
yydhYYDH/alpha101
ryckli/CryptoAgentPro.beta
```

AlphaPilot only stores URL/license/summary/citation metadata for these
references. It does not copy external code or long source text.

## V13.7.3 External Quant Platform Reference Notes

V13.7.3 records additional external platform references for future AlphaPilot
architecture work:

```text
QuantFans/quantdigger
brokermr810/QuantDinger
HelloGitHub issue #3107
Sina quant open-source roundup
```

The stored note is `docs/future-quant-platform-reference-notes.md`.

It captures:

```text
event-driven strategy lifecycle ideas
multi-strategy and portfolio-level backtest artifact ideas
local-first AI trading OS architecture ideas
agent gateway and audit-first boundary ideas
public tool radar categories for future research
```

This is reference-only. AlphaPilot does not copy external source code, install
new dependencies, enable exchange keys, call Trade API or Withdraw API, read
real accounts or positions, create orders, enter Dry-run, live trade, or auto
trade.

The overlay adds:

```text
cross-sectional ranks
time-series ranks
rolling return-volume correlation
decay-style return and volume pressure
rebound pressure
exhaustion pressure
liquidity quality
```

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_7_external_alpha_overlay.ps1
```

Generate from existing local public data:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_7_external_alpha_overlay.ps1 -Run
```

Outputs:

```text
alphapilot/factors/alpha101_style_overlay.py
alphapilot/reports/generate_v13_5_7_external_alpha_overlay_report.py
scripts/run_v13_5_7_external_alpha_overlay.ps1
reports/v13_5_7_external_alpha_overlay_report.json
reports/v13_5_7_external_alpha_overlay_summary.md
reports/v13_5_7_alpha_overlay_candidates.json
docs/V13.5.7-external-alpha-overlay.md
```

Current V13.5.7 decision:

```text
localPaperWatchApproved = true
localPaperWatchPoolId = 4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24
newFormalPaperCandidateApproved = false
exchangeDryRunApproved = false
liveTradingApproved = false
```

Best overlay pool:

```text
trades = 145
winRate = 58.6207%
rewardRiskRatio = 1.8207
profitFactor = 2.5793
maxDrawdown = 38.3157%
recent20ProfitFactor = 3.2286
observedToCostAdjusted2RCloseness = 0.956639
```

Interpretation: V13.5.7 finds a useful 4h short-exhaustion local paper watch
pool, but drawdown remains high and the result requires fresh forward
confirmation. It is not approved for exchange Dry-run or live trading.

V13.5.7 remains research-only:

```text
no Trade API
no Withdraw API
no API key storage
no real account reads
no real position reads
no real orders
no automatic trading
exchange Dry-run remains disabled
```

## V13.5.8 Adaptive ML Factor Discovery

V13.5.8 adds an auditable adaptive machine-learning layer. It lets AlphaPilot
learn factor-threshold rules from prior folds and validate those rules on later
folds. This creates a foundation for strategy evolution without granting the
model any trading authority.

The current runtime does not include sklearn/xgboost/lightgbm/catboost, so
V13.5.8 uses a lightweight pandas/numpy learner:

```text
train-only context discovery
factor quantile thresholds
walk-forward validation
fold stability checks
strategy evolution sample schema
```

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_8_adaptive_ml_factor_report.ps1
```

Generate from existing local public data:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_8_adaptive_ml_factor_report.ps1 -Run
```

Outputs:

```text
alphapilot/ml_gate/adaptive_factor_learner.py
alphapilot/ml_gate/strategy_evolution_schema.py
alphapilot/reports/generate_v13_5_8_adaptive_ml_factor_report.py
scripts/run_v13_5_8_adaptive_ml_factor_report.ps1
reports/v13_5_8_adaptive_ml_factor_report.json
reports/v13_5_8_adaptive_ml_factor_summary.md
reports/v13_5_8_adaptive_ml_candidates.json
reports/v13_5_8_strategy_evolution_sample_schema.json
docs/V13.5.8-adaptive-ml-factor-discovery.md
```

Current V13.5.8 decision:

```text
adaptiveMLComputed = true
targetRMultipleUnchanged = true
localPaperWatchApproved = false
localPaperWatchPoolId = null
newFormalPaperCandidateApproved = false
exchangeDryRunApproved = false
liveTradingApproved = false
```

Best full adaptive candidate:

```text
pool = 1h:adaptive_ml_all_high_reward:sl0.025:h30
selectedTrades = 1275
winRate = 36.7059%
rewardRiskRatio = 1.6143
profitFactor = 0.9362
totalReturn = -86.5794%
maxDrawdown = 98.3195%
```

Interpretation: the adaptive learner improved some baselines and found
positive small-sample rules, but the full walk-forward candidate is still
negative. V13.5.8 does not approve a new local paper watch candidate. The
current actionable research line remains the V13.5.7 fixed 4h alpha overlay,
which still requires fresh forward confirmation.

V13.5.8 also adds `strategy_evolution_sample_v1` so future local paper outcomes
and manual trade-review outcomes can become research samples. These samples can
only support offline retraining after validation; they must not trigger order
creation or bypass risk review.

V13.5.8 remains research-only:

```text
no Trade API
no Withdraw API
no API key storage
no real account reads
no real position reads
no real orders
no automatic trading
exchange Dry-run remains disabled
```

## Future Live Trading Reference Notes

The repository now stores a reference-only design note for
`ryckli/CryptoAgentPro.beta`:

```text
docs/future-live-trading-reference-cryptoagentpro-beta.md
```

It records future-review concepts such as API key configuration, order
endpoints, emergency close, testnet mode, automatic mode, risk gateway,
strategy scheduling, and AI trend analysis. This is documentation only. It does
not add Trade API, Withdraw API, exchange credentials, account reads, position
reads, order creation, emergency close, testnet execution, or automatic trading.

The repository also stores a reference-only note for `yydhYYDH/alpha101`:

```text
docs/future-factor-research-reference-alpha101.md
```

This records factor-panel, expression-grammar, factor-search, IC-style
evaluation, and research-service ideas for future AlphaPilot factor work. It
does not import alpha101, copy source code, create strategies, or approve
execution.

The combined external reference index is:

```text
docs/external-repository-reference-index.md
```

## V13.5.9 Strategy Control Tower and Local Paper Router

V13.5.9 adds a local-paper-only control tower that coordinates existing research
outputs into strategy states and router intents.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_9_strategy_control_tower.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_9_strategy_control_tower.ps1 -Run
```

Outputs:

```text
alphapilot/control_tower/strategy_control_tower.py
alphapilot/reports/generate_v13_5_9_strategy_control_tower_report.py
scripts/run_v13_5_9_strategy_control_tower.ps1
reports/v13_5_9_strategy_control_tower_report.json
reports/v13_5_9_strategy_control_tower_summary.md
reports/v13_5_9_local_paper_router_intents.json
reports/v13_5_9_external_reference_index.json
docs/V13.5.9-strategy-control-tower-local-paper-router.md
```

V13.5.9 current routing decision:

```text
V13.5.7 alpha overlay = active local paper watch
V13.5.8 adaptive ML = observer only
exchange Dry-run review = not ready
live trading = not approved
```

Router intents are not orders. V13.5.9 does not add Trade API, Withdraw API,
exchange credentials, account reads, position reads, order creation, emergency
close, testnet execution, or automatic trading.

## V13.5.10 Continuous Learning Loop

V13.5.10 starts the AlphaPilot continuous learning loop by converting local
paper outcomes into strategy evolution samples and a retraining-readiness gate.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_10_continuous_learning_loop.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_10_continuous_learning_loop.ps1 -Run
```

Outputs:

```text
alphapilot/learning_loop/strategy_learning_loop.py
alphapilot/reports/generate_v13_5_10_continuous_learning_loop_report.py
scripts/run_v13_5_10_continuous_learning_loop.ps1
reports/v13_5_10_continuous_learning_loop_report.json
reports/v13_5_10_continuous_learning_loop_summary.md
reports/v13_5_10_strategy_evolution_dataset.json
reports/v13_5_10_learning_state.json
docs/V13.5.10-continuous-learning-loop.md
```

Current learning-loop result:

```text
newTrainingSamplesFromPaper = 41
usableTrainingSamplesFromPaper = 41
activeStrategySamplesFromPaper = 0
readyForRetraining = false
continueLocalPaperMonitoring = true
exchange Dry-run = not approved
live trading = not approved
```

The 41 available paper samples belong to an older V13.5.1 candidate. The current
V13.5.7 active local paper watch has no closed paper samples yet, so V13.5.10
does not retrain a model.

Future data expansion can include larger public sample pools across crypto,
A-shares, Hong Kong stocks, US equities, ETFs, and indices. Cross-market samples
must be stored as research data with explicit labels and must not become crypto
execution commands.

V13.5.10 does not add Trade API, Withdraw API, API key storage, real account
reads, real position reads, real orders, emergency close, testnet execution, or
automatic trading.

## V13.5.11 Cross-Market Public Data Smoke

V13.5.11 adds a public cross-market data smoke test so AlphaPilot can begin
expanding its research sample base beyond crypto.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_11_cross_market_data_smoke.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_11_cross_market_data_smoke.ps1 -Run
```

Outputs:

```text
alphapilot/cross_market/public_market_data.py
alphapilot/reports/generate_v13_5_11_cross_market_data_smoke_report.py
scripts/run_v13_5_11_cross_market_data_smoke.ps1
reports/v13_5_11_cross_market_public_data_smoke_report.json
reports/v13_5_11_cross_market_public_data_smoke_summary.md
docs/V13.5.11-cross-market-public-data-smoke.md
user_data/cross_market_data/
```

Default smoke symbols cover A-share, Hong Kong, US ETF, and index references:

```text
600519.SS, 000001.SZ, 0700.HK, 9988.HK, SPY, QQQ, ^HSI, ^GSPC
```

Raw OHLCV files are cached locally under `user_data/cross_market_data/` and are
not committed to Git. Cross-market samples are research references for regime,
volatility, liquidity, and factor robustness. They are not crypto execution
commands and they do not approve exchange Dry-run or live trading.

V13.5.11 does not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, or automatic
trading.

## V13.5.12 Active Alpha Overlay Replay

V13.5.12 rebuilds the current V13.5.7 active alpha overlay pool into a
single-trade event log and replays it through the local paper sandbox.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_12_active_alpha_overlay_replay.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_12_active_alpha_overlay_replay.ps1 -Run
```

Outputs:

```text
alphapilot/reports/generate_v13_5_12_active_alpha_overlay_replay_report.py
scripts/run_v13_5_12_active_alpha_overlay_replay.ps1
reports/v13_5_12_active_alpha_overlay_replay_report.json
reports/v13_5_12_active_alpha_overlay_replay_summary.md
reports/v13_5_12_active_alpha_overlay_signal_log.json
reports/v13_5_12_active_alpha_overlay_paper_ledger.json
docs/V13.5.12-active-alpha-overlay-replay.md
```

Current result:

```text
activeOverlayEventCount = 145
filledSignalCount = 131
tradeCount = 131
winRate = 58.7786%
profitFactor = 2.5656
rewardRiskRatio = 1.7992
maxDrawdown = 6.82632%
```

This is the first active-strategy replay that looks operationally useful. It is
still historical replay, not forward validation. The next gate is fresh forward
local paper monitoring after the active pool selection date.

V13.5.12 does not add Trade API, Withdraw API, API key storage, real account
reads, real position reads, real orders, exchange Dry-run execution, live
trading, or automatic trading.

## V13.5.13 Forward Readiness Monitor

V13.5.13 checks whether enough post-selection public candles exist to produce
closed forward local paper samples for the active V13.5.7 strategy.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_13_forward_readiness_monitor.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_13_forward_readiness_monitor.ps1 -Run
```

Outputs:

```text
alphapilot/reports/generate_v13_5_13_forward_readiness_monitor.py
scripts/run_v13_5_13_forward_readiness_monitor.ps1
reports/v13_5_13_forward_readiness_monitor_report.json
reports/v13_5_13_forward_readiness_monitor_summary.md
docs/V13.5.13-forward-readiness-monitor.md
```

Current readiness:

```text
selectionTime = 2026-07-05T20:13:33.701790+00:00
requiredHorizonHours = 96
earliestClosedSampleTime = 2026-07-09T20:13:33.701790+00:00
latestLocalCandle = 2026-07-05T16:00:00+00:00
readyPairCount = 0
readyForForwardLocalPaperRefresh = false
```

This is a time/horizon constraint. The active 4h strategy cannot produce closed
post-selection samples until enough 4h candles exist after selection.

V13.5.13 does not add Trade API, Withdraw API, API key storage, real account
reads, real position reads, real orders, exchange Dry-run execution, live
trading, or automatic trading.

## V13.5.14 Historical Robustness Expansion

V13.5.14 expands historical diagnostics for the fixed active V13.5.7 alpha
overlay pool without changing its parameters:

```text
4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24
```

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_14_historical_robustness_expansion.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_14_historical_robustness_expansion.ps1 -Run
```

Outputs:

```text
alphapilot/reports/generate_v13_5_14_historical_robustness_expansion_report.py
scripts/run_v13_5_14_historical_robustness_expansion.ps1
reports/v13_5_14_historical_robustness_expansion_report.json
reports/v13_5_14_historical_robustness_expansion_summary.md
reports/v13_5_14_active_strategy_historical_signal_log.json
docs/V13.5.14-historical-robustness-expansion.md
```

This report uses existing OKX public historical crypto data and the V13.5.11
cross-market Yahoo public chart cache for A-share, Hong Kong, US ETF, and index
context. Cross-market data is used as factor and regime research context only.
It is not used to create crypto execution commands.

Optional 2020-to-present Top100 multi-exchange public data expansion:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_historical_robustness_data.ps1 -UseTop100 -Exchanges "okx,binance,bybit" -Timeframes "4h,1d" -Timerange "20200101-" -BatchSize 20 -Prepend
```

Add `-Run` only when intentionally downloading public data. The downloader is
batched because Top100 x multiple exchanges x six years can be slow and some
symbols will be unavailable on some exchanges.

V13.5.14 also adds walk-forward review, market-state slices, stress tests, and
lightweight factor outcome separation for machine-learning research. These are
research diagnostics only; they do not change strategy parameters or create
orders.

V13.5.14 does not replace V13.5.13 forward validation. It can improve historical
robustness evidence, but the active 4h strategy still needs closed
post-selection forward samples before any exchange Dry-run review.

V13.5.14 does not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, exchange
Dry-run execution, live trading, or automatic trading.

## V13.5.15 Multi-Exchange Historical Data Coverage

V13.5.15 turns the 2020-to-present data expansion step into an auditable local
coverage report before changing any strategy logic.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_15_multi_exchange_data_coverage.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_15_multi_exchange_data_coverage.ps1 -Run
```

Outputs:

```text
alphapilot/reports/generate_v13_5_15_multi_exchange_data_coverage_report.py
scripts/run_v13_5_15_multi_exchange_data_coverage.ps1
reports/v13_5_15_multi_exchange_data_coverage_report.json
reports/v13_5_15_multi_exchange_data_coverage_summary.md
docs/V13.5.15-multi-exchange-data-coverage.md
```

The report scans local public OHLCV files for OKX, Binance, and Bybit across
the Top 100 USDT swap research universe and the 4h / 1d timeframes. It records
which files are actually present, row counts, first/last timestamps, and core
BTC/ETH/SOL multi-exchange readiness.

V13.5.15 records the practical download reality: long Top100 2020-to-present
downloads may complete partially and must be reported honestly instead of
treated as full validation. Binance and Bybit core BTC/ETH/SOL files provide a
first independent exchange-path sample; the strategy feature panel remains
OKX-centered until an exchange-aware feature layer is built.

V13.5.15 does not change strategy parameters, run Dry-run, connect to private
exchange endpoints, save API keys, read real accounts or positions, create
orders, or enable automatic trading.

## V13.5.16 Core Multi-Exchange Replay

V13.5.16 points the existing feature and event pipeline at exchange-specific
local public data directories and replays the fixed active V13.5.7 pool on
BTC/ETH/SOL across OKX, Binance, and Bybit.

Active pool:

```text
4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24
```

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_16_core_multi_exchange_replay.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_16_core_multi_exchange_replay.ps1 -Run
```

Outputs:

```text
alphapilot/derivatives/exchange_feature_panel.py
alphapilot/reports/generate_v13_5_16_core_multi_exchange_replay_report.py
scripts/run_v13_5_16_core_multi_exchange_replay.ps1
reports/v13_5_16_core_multi_exchange_replay_report.json
reports/v13_5_16_core_multi_exchange_replay_summary.md
reports/v13_5_16_core_multi_exchange_signal_log.json
docs/V13.5.16-core-multi-exchange-replay.md
```

This report keeps parameters fixed. It checks whether the active research pool
has enough historical events across independent exchange public-data paths. It
does not fit, optimize, or approve an execution path.

V13.5.16 does not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, exchange
Dry-run execution, live trading, or automatic trading.

## V13.5.17 Available-Universe Exchange Replay

V13.5.17 expands the fixed active-pool replay from BTC/ETH/SOL to every local
public 4h futures file currently available per exchange.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_17_available_universe_exchange_replay.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_17_available_universe_exchange_replay.ps1 -Run
```

Outputs:

```text
alphapilot/reports/generate_v13_5_17_available_universe_exchange_replay_report.py
scripts/run_v13_5_17_available_universe_exchange_replay.ps1
reports/v13_5_17_available_universe_exchange_replay_report.json
reports/v13_5_17_available_universe_exchange_replay_summary.md
reports/v13_5_17_available_universe_exchange_signal_log.json
docs/V13.5.17-available-universe-exchange-replay.md
```

This version uses only already downloaded public files. It does not trigger
another long Top100 download. The goal is to measure whether the fixed active
pool naturally gains sample size and exchange balance from local data before
any next data-expansion command is run.

V13.5.17 does not change strategy parameters, run Dry-run, connect to private
exchange endpoints, save API keys, read real accounts or positions, create
orders, or enable automatic trading.

## V13.5.18 Non-OKX Expansion Replay

V13.5.18 expands Binance and Bybit public 4h futures data to the Top20 research
subset in small resumable batches, then reruns the fixed active-pool replay.

Data expansion command used:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_historical_robustness_data.ps1 -Pairs "<Top20 research subset>" -Exchanges "binance,bybit" -Timeframes "4h" -Timerange "20200101-" -BatchSize 5 -Prepend -Run
```

Generate replay report:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_18_non_okx_expansion_replay.ps1 -Run
```

Outputs:

```text
alphapilot/reports/generate_v13_5_18_non_okx_expansion_replay_report.py
scripts/run_v13_5_18_non_okx_expansion_replay.ps1
reports/v13_5_18_non_okx_expansion_replay_report.json
reports/v13_5_18_non_okx_expansion_replay_summary.md
reports/v13_5_18_non_okx_expansion_signal_log.json
docs/V13.5.18-non-okx-expansion-replay.md
```

V13.5.18 is still research-only. It does not tune parameters, run exchange
Dry-run, save API keys, read accounts, create orders, or enable automatic
trading.

## V13.5.19 Risk-Normalized Portfolio Replay

V13.5.19 evaluates the V13.5.18 historical signal log with fixed portfolio-level
throttles in R-multiple space. The active entry rules and 2R target are not
changed.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_19_risk_normalized_portfolio_replay.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_19_risk_normalized_portfolio_replay.ps1 -Run
```

Outputs:

```text
alphapilot/paper_sandbox/risk_normalized_replay.py
alphapilot/reports/generate_v13_5_19_risk_normalized_portfolio_replay_report.py
scripts/run_v13_5_19_risk_normalized_portfolio_replay.ps1
reports/v13_5_19_risk_normalized_portfolio_replay_report.json
reports/v13_5_19_risk_normalized_portfolio_replay_summary.md
reports/v13_5_19_best_policy_selected_signals.json
docs/V13.5.19-risk-normalized-portfolio-replay.md
```

The local paper refresh review gate is intentionally stricter than a pure
profit-factor check: enough trades, enough exchanges, enough pairs, reward/risk
near 2R, controlled max drawdown, and controlled consecutive losses. Passing
this gate is not exchange Dry-run approval.

V13.5.19 does not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, exchange
Dry-run execution, live trading, or automatic trading.

## V13.5.20 Exit-Aware Loss Cooldown

V13.5.20 evaluates portfolio loss-cooldown policies that only activate after a
selected historical trade closes. This avoids future leakage: the replay does
not know a loss until `exitDate`.

The active entry rules and 2R target are not changed.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_20_exit_aware_loss_cooldown.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_20_exit_aware_loss_cooldown.ps1 -Run
```

Outputs:

```text
alphapilot/paper_sandbox/risk_normalized_replay.py
alphapilot/reports/generate_v13_5_20_exit_aware_loss_cooldown_report.py
scripts/run_v13_5_20_exit_aware_loss_cooldown.ps1
reports/v13_5_20_exit_aware_loss_cooldown_report.json
reports/v13_5_20_exit_aware_loss_cooldown_summary.md
reports/v13_5_20_best_exit_aware_policy_selected_signals.json
docs/V13.5.20-exit-aware-loss-cooldown.md
```

Current best policy:

```text
policyId: pair_loss_exit_21d
tradeCount: 412
winRatePct: 50.9709
profitFactor: 1.873058
rewardRiskRatio: 1.801704
maxDrawdownR: 13.0628
maxConsecutiveLosses: 11
uniquePairs: 36
uniqueExchanges: 3
readyForLocalPaperRefreshReview: true
readyForExchangeDryRunReview: false
```

V13.5.20 clears the local paper refresh review gate, but it does not approve
exchange Dry-run or live trading. It does not add Trade API, Withdraw API, API
key storage, broker credentials, real account reads, real position reads, real
orders, exchange Dry-run execution, live trading, or automatic trading.

## V13.5.21 Local Paper Refresh Candidate

V13.5.21 packages the V13.5.20 selected signals into the existing local paper
sandbox ledger. It validates local simulation mechanics only.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_21_local_paper_refresh_candidate.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_21_local_paper_refresh_candidate.ps1 -Run
```

Outputs:

```text
alphapilot/reports/generate_v13_5_21_local_paper_refresh_candidate_report.py
scripts/run_v13_5_21_local_paper_refresh_candidate.ps1
reports/v13_5_21_local_paper_refresh_candidate_report.json
reports/v13_5_21_local_paper_refresh_candidate_summary.md
reports/v13_5_21_local_paper_refresh_candidate_ledger.json
reports/v13_5_21_local_paper_refresh_candidate_package.json
docs/V13.5.21-local-paper-refresh-candidate.md
```

Current result:

```text
candidateId: 4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24
selectedPolicyId: pair_loss_exit_21d
targetRMultiple: 2.0
maxConcurrentPositions: 8
filledSignalCount: 409
skippedSignalCount: 3
winRatePct: 51.1002
profitFactor: 1.9588
rewardRiskRatio: 1.8744
maxDrawdownPct: 11.841614
localPaperRefreshCandidateReady: true
readyForExchangeDryRunReview: false
```

V13.5.21 does not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, exchange
Dry-run execution, live trading, or automatic trading.

## V13.5.22 Alpha191 Factor Extraction

V13.5.22 extracts a copyright-safe factor research catalog from the
user-provided local PDF `Alpha191因子公式小白学习手册.pdf`.

This version stores only source metadata, citation, factor IDs, categories,
operator tags, required fields, short implementation notes, and crypto
adaptation clusters. It does not store complete formulas, long source
explanations, raw PDF text, or copied pages.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_22_alpha191_factor_extraction.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_22_alpha191_factor_extraction.ps1 -Run
```

Outputs:

```text
alphapilot/reports/generate_v13_5_22_alpha191_factor_extraction_report.py
scripts/run_v13_5_22_alpha191_factor_extraction.ps1
reports/v13_5_22_alpha191_factor_extraction_report.json
reports/v13_5_22_alpha191_factor_extraction_summary.md
reports/v13_5_22_alpha191_factor_candidate_catalog.json
docs/V13.5.22-alpha191-factor-extraction.md
```

Parsed category counts:

```text
量价相关/协同: 47
动量反转/均值回复: 46
成交量/资金活跃: 36
波动振幅/日内结构: 29
综合价格形态: 13
市场联动/回归: 8
排序位置/相对强弱: 6
条件统计/规则触发: 6
```

V13.5.22 is a research metadata step only. It does not change strategy rules,
run backtests, change local paper trading, add Trade API, add Withdraw API,
store API keys, read real accounts, read real positions, create orders, run
exchange Dry-run, enable live trading, or enable automatic trading.

## V13.5.23 Alpha191 Crypto-Safe Subset Replay

V13.5.23 implements a small Alpha191-inspired crypto-safe factor subset and
tests it against the existing local historical replay gates. It does not copy
Alpha191 formulas. It uses V13.5.22 metadata as a research guide and implements
compact public-OHLCV-derived features that can be audited directly in
AlphaPilot.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_23_alpha191_crypto_subset_replay.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_23_alpha191_crypto_subset_replay.ps1 -Run
```

Outputs:

```text
alphapilot/factors/alpha191_crypto_safe_subset.py
alphapilot/reports/generate_v13_5_23_alpha191_crypto_subset_replay_report.py
scripts/run_v13_5_23_alpha191_crypto_subset_replay.ps1
reports/v13_5_23_alpha191_crypto_subset_replay_report.json
reports/v13_5_23_alpha191_crypto_subset_replay_summary.md
reports/v13_5_23_alpha191_crypto_subset_signal_log.json
reports/v13_5_23_alpha191_crypto_subset_selected_signals.json
docs/V13.5.23-alpha191-crypto-safe-subset-replay.md
```

Current V13.5.23 result:

```text
Best raw candidate: 4h:a191_short_exhaustion_quality_v01:sl0.06:h24
Raw trades: 3736
Raw winRatePct: 40.5514
Raw profitFactor: 1.163
Raw rewardRiskRatio: 1.705
Raw maxDrawdownPct: 99.7438
Raw gate passed: false

Best exit-aware policy: global_loss_exit_pause_8h
Exit-aware trades: 1412
Exit-aware profitFactor: 1.307052
Exit-aware rewardRiskRatio: 1.688983
Exit-aware maxDrawdownR: 91.7798
Exit-aware gate passed: false

Local paper filled signals: 1112
Local paper winRatePct: 42.8957
Local paper profitFactor: 1.3785
Local paper rewardRiskRatio: 1.8351
Local paper maxDrawdownPct: 51.845183
Local paper gate passed: false
```

Decision:

```text
alpha191SubsetImplemented = true
rawReplayGatePassed = false
exitAwareGatePassed = false
localPaperGatePassed = false
readyForForwardRefreshComparison = false
exchangeDryRunApproved = false
liveTradingApproved = false
nextAction = keep_alpha191_subset_as_research_only_and_do_not_replace_v13_5_21
```

Interpretation: V13.5.23 is useful research because it proves this first
Alpha191-inspired subset does not clear the existing AlphaPilot gates. It should
remain observer/research context. It does not replace the V13.5.21 local paper
refresh candidate.

V13.5.23 does not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, exchange
Dry-run execution, live trading, or automatic trading.

## V13.7.1 Strategy Runtime Data Contract

V13.7.1 creates a read-only local data contract for the AlphaPilot desktop and
mobile consoles. It does not change strategy rules, does not run a new
backtest, does not download market data, and does not connect to exchange
private APIs.

Run the contract builder:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_runtime_contract.ps1
```

Outputs:

```text
alphapilot/runtime/runtime_contract.py
alphapilot/reports/generate_v13_7_1_runtime_contract.py
scripts/build_runtime_contract.ps1
reports/runtime_status.json
reports/signal_tape.json
reports/paper_observation_ledger.json
docs/V13.7.1-strategy-runtime-data-contract.md
```

The runtime contract currently standardizes the V13.5.21 local paper refresh
candidate as the active strategy and keeps the V13.5.23 Alpha191 subset as a
research observer. The output is meant for dashboard display:

```text
activeStrategy = V13.5.21 local paper refresh candidate
signalTapeCount = 412
paperObservationCount = 409
runtimeHealth = runtime_contract_ready
```

This is not exchange Dry-run approval. It is not live trading approval. It is a
local file bridge that lets the Control Console and mobile app display strategy
status, historical signal tape, and simulated paper observation context without
creating any execution capability.

V13.7.1 does not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, exchange
Dry-run execution, live trading, or automatic trading.

## V13.7.4 Strategy Artifact Center

V13.7.4 adds a read-only strategy artifact index for the desktop Control Console
and mobile console.

Run the artifact index builder:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_strategy_artifact_index.ps1
```

Outputs:

```text
alphapilot/artifacts/strategy_artifact_index.py
alphapilot/reports/generate_v13_7_4_strategy_artifact_index.py
scripts/build_strategy_artifact_index.ps1
reports/strategy_artifact_index.json
docs/V13.7.4-strategy-artifact-center.md
```

The index scans local `reports/*.json` files and classifies strategy artifacts
into conservative research-routing tiers:

```text
paper_observation_ready
research_watchlist
needs_review
archived_or_failed
blocked_by_safety_review
```

Readiness tiers are not trading approval. V13.7.4 does not download data, run
backtests, call exchanges, connect private APIs, create orders, run dry-run,
run live trading, or enable automatic trading.

## V13.7.13 Backtest Task Completion

V13.7.13 completes the six `needs_backtest` tasks that appeared in the
V13.7.12 research task board.

Run the completion report:

```powershell
python -m alphapilot.reports.generate_v13_7_13_backtest_task_completion_report
```

Outputs:

```text
reports/v13_7_13_factor_panel_report.json
reports/v13_7_13_factor_evaluation_report.json
reports/v13_7_13_derivatives_ml_strategy_1h_broad_report.json
reports/v13_7_13_derivatives_ml_strategy_4h_broad_report.json
reports/v13_7_13_adaptive_ml_factor_report.json
reports/v13_7_13_backtest_task_completion_report.json
reports/v13_7_13_backtest_task_completion_summary.md
docs/V13.7.13-backtest-task-completion.md
```

Result:

```text
completedTaskCount: 6
paperOrShadowApprovedCount: 0
failedOrNotReadyCount: 6
dryRunApproved: false
liveTradingApproved: false
```

Interpretation: the six tasks are no longer vague backlog items. They have
been audited or rerun with local public data evidence, and none of them clears
the AlphaPilot observation, paper, exchange Dry-run, or live trading boundary.
The useful result is negative evidence that should guide the next strategy
specification instead of encouraging overfit tuning.

V13.7.13 does not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, exchange
Dry-run execution, live trading, or automatic trading.

## Third-Party Reference Snapshot: TradingAgents

AlphaPilot now keeps a local third-party reference snapshot of
`tauricresearch/tradingagents`:

```text
third_party/tradingagents/
third_party/tradingagents/ALPHAPILOT_SNAPSHOT.md
third_party/tradingagents/LICENSE
```

The snapshot is Apache-2.0 licensed and keeps upstream attribution, license, and
the captured commit metadata. AlphaPilot uses it only as an architecture
reference for multi-agent research review, structured reports, checkpointing,
and decision-memory ideas.

Important boundary: the snapshot is not an execution adapter. Upstream
transaction-oriented terminology must be mapped into AlphaPilot research-only
language before any idea is reused. The snapshot must not create orders, connect
Trade API, connect Withdraw API, store exchange API keys, read real account
data, or automate trading.

## V13.7.14 Multi-Agent Strategy Review

V13.7.14 adds a deterministic, research-only multi-agent strategy review layer
inspired by the TradingAgents architecture.

Run the review:

```powershell
python -m alphapilot.reports.generate_v13_7_14_multi_agent_strategy_review
```

Outputs:

```text
alphapilot/reports/generate_v13_7_14_multi_agent_strategy_review.py
reports/v13_7_14_multi_agent_strategy_review_report.json
reports/v13_7_14_multi_agent_strategy_review_summary.md
docs/V13.7.14-multi-agent-strategy-review.md
```

Reviewer roles:

```text
data_quality_reviewer
backtest_validity_reviewer
risk_reviewer
skeptic_reviewer
research_committee
```

Result:

```text
reviewedSubjectCount: 6
keep_researching: 3
reject_for_now: 3
paperObservationCandidateCount: 0
dryRunApproved: false
liveTradingApproved: false
```

V13.7.14 does not call an LLM. It does not produce trading commands, does not
approve paper observation, does not approve exchange Dry-run, and does not
approve live trading. It only transforms existing V13.7.13 evidence into a
clearer research committee-style review.

## V13.7.15-V13.7.18 Strategy Learning Loop

V13.7.15-V13.7.18 turns the multi-agent review output into a deterministic
research learning loop:

```powershell
python -m alphapilot.reports.generate_v13_7_15_to_18_strategy_learning_loop
```

Outputs:

```text
alphapilot/reports/generate_v13_7_15_to_18_strategy_learning_loop.py
reports/v13_7_15_strategy_learning_loop_report.json
reports/v13_7_15_strategy_learning_loop_summary.md
reports/v13_7_16_strategy_refactor_candidates_report.json
reports/v13_7_16_strategy_refactor_candidates_summary.md
reports/v13_7_17_regime_filtered_experiment_specs_report.json
reports/v13_7_17_regime_filtered_experiment_specs_summary.md
reports/v13_7_18_paper_observation_rereview_report.json
reports/v13_7_18_paper_observation_rereview_summary.md
docs/V13.7.15-strategy-learning-loop.md
docs/V13.7.16-strategy-refactor-candidates.md
docs/V13.7.17-regime-filtered-experiment-specs.md
docs/V13.7.18-paper-observation-rereview.md
```

Version flow:

- V13.7.15 builds a strategy learning ledger, graveyard, research watchlist,
  and factor memory from V13.7.14 review evidence.
- V13.7.16 converts that memory into refactor candidates instead of simply
  adding more raw strategies.
- V13.7.17 turns the best candidates into explicit low-frequency and
  regime-filtered experiment specs.
- V13.7.18 re-reviews paper-observation readiness and keeps all candidates in
  research-backtest-only status until deterministic evidence exists.

Result:

```text
learningItemCount: 6
graveyardCount: 3
researchWatchlistCount: 3
refactorCandidateCount: 4
experimentSpecCount: 3
paperObservationApprovedCount: 0
dryRunApproved: false
liveTradingApproved: false
```

Recommended next executable research step:

```text
Implement a deterministic backtest for lf_factor_confluence_regime_filter_4h_v0_1 first.
```

V13.7.15-V13.7.18 do not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, exchange
Dry-run execution, live trading, or automatic trading.

## V13.7.19 LF Factor Confluence Deterministic Backtest

V13.7.19 implements the first deterministic research backtest requested by
V13.7.18:

```powershell
python -m alphapilot.reports.generate_v13_7_19_lf_factor_confluence_backtest
```

Outputs:

```text
alphapilot/low_frequency/factor_confluence_backtest.py
alphapilot/reports/generate_v13_7_19_lf_factor_confluence_backtest.py
reports/v13_7_19_lf_factor_confluence_backtest_report.json
reports/v13_7_19_lf_factor_confluence_backtest_summary.md
docs/V13.7.19-lf-factor-confluence-backtest.md
```

Result:

```text
experimentId: lf_factor_confluence_regime_filter_4h_v0_1
tradeCount: 92
winRatePct: 39.1304
profitFactor: 1.1694
targetRewardRiskRatio: 2.0
totalReturnPct: 9.7877
maxDrawdownPct: 18.8774
walkForwardValidationPositive: false
paperObservationApproved: false
dryRunApproved: false
liveTradingApproved: false
```

The total sample is promising but the 2023-2024 walk-forward validation split
is negative, so the candidate remains research-only. The 2R target was not
weakened to rescue the result.

V13.7.19 does not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, exchange
Dry-run execution, live trading, or automatic trading.

## V13.7.20 Five Strategy Candidate Factory

V13.7.20 expands the deterministic low-frequency research layer into a batch
candidate factory. It searches local public OKX futures OHLCV from 2020-2026
for fixed 2R strategy candidates, then approves at most five candidates for
local paper-observation review only.

```powershell
python -m alphapilot.reports.generate_v13_7_20_five_strategy_candidate_factory
```

Outputs:

```text
alphapilot/low_frequency/strategy_candidate_factory.py
alphapilot/reports/generate_v13_7_20_five_strategy_candidate_factory.py
reports/v13_7_20_five_strategy_candidate_factory_report.json
reports/v13_7_20_five_strategy_candidate_factory_summary.md
docs/V13.7.20-five-strategy-candidate-factory.md
```

Result:

```text
candidateCount: 120
approvedCount: 5
targetApprovedCount: 5
targetRewardRiskRatio: 2.0
paperObservationApprovedCount: 5
dryRunApproved: false
liveTradingApproved: false
```

Approved local paper-observation candidates:

```text
lf_research_candidate_089: 1d trend breakout confirmation ATR2.0
  trades 319, winRatePct 45.4545, PF 1.5035, returnPct 80.2621, maxDD 21.4697
lf_research_candidate_117: 1d sideways oversold reclaim ATR1.2
  trades 36, winRatePct 58.3333, PF 2.4289, returnPct 21.7981, maxDD 6.8439
lf_research_candidate_115: 1d sideways oversold reclaim ATR1.0
  trades 38, winRatePct 55.2632, PF 2.2125, returnPct 21.0635, maxDD 7.7808
lf_research_candidate_090: 1d trend squeeze breakout ATR2.0
  trades 207, winRatePct 43.4783, PF 1.3856, returnPct 40.6901, maxDD 20.0035
lf_research_candidate_108: 1d broad squeeze breakout ATR2.0
  trades 220, winRatePct 42.2727, PF 1.3152, returnPct 36.4671, maxDD 20.8539
```

These candidates are not live strategies. They are local paper-observation
research candidates. Candidate 089 has a barely positive 2025-2026 test split,
and candidates 115/117 have thin train samples, so they require forward paper
observation before any future exchange Dry-run review.

V13.7.20 does not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, exchange
Dry-run execution, live trading, or automatic trading.

## V13.7.21 Paper Observation Task Pack

V13.7.21 turns the five V13.7.20 research candidates into local
paper-observation tasks. This is the bridge between historical research and
forward observation: the strategies still cannot create orders, cannot run
exchange Dry-run, and cannot trade automatically.

```powershell
python -m alphapilot.reports.generate_v13_7_21_paper_observation_task_pack
```

Outputs:

```text
alphapilot/reports/generate_v13_7_21_paper_observation_task_pack.py
reports/v13_7_21_paper_observation_task_pack_report.json
reports/v13_7_21_paper_observation_task_pack_summary.md
docs/V13.7.21-paper-observation-task-pack.md
```

Result:

```text
taskCount: 5
plannedPaperObservationCount: 5
targetClosedSamplesTotal: 130
dryRunApproved: false
liveTradingApproved: false
```

Each task includes:

- observation days and target closed sample count
- weak points from walk-forward splits
- recommended pairs and pairs requiring review
- daily log fields
- promotion criteria
- rejection criteria
- blocked actions: exchange Dry-run, live trading, order creation, automatic trading, API key storage

V13.7.21 does not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, exchange
Dry-run execution, live trading, or automatic trading.

## V13.7.40 Short-Cycle Parameter Search

V13.7.40 searches for short-cycle public-OHLCV research candidates with a fixed
2R target. It expands the historical dataset with Binance Vision public futures
klines from 2020-2026, then evaluates 15m / 30m / 1h candidate families. The
useful result came from 1h short-side upper-wick rejection candidates with a
train-segment-only asset filter.

```powershell
python -m alphapilot.reports.download_binance_vision_klines
python -m alphapilot.reports.generate_v13_7_40_short_cycle_parameter_search --data-path user_data/data/binance_vision/futures --timerange 20200101- --timeframes 1h
```

Key outputs:

```text
alphapilot/data_expansion/binance_vision_klines.py
alphapilot/short_cycle/parameter_search.py
alphapilot/reports/generate_v13_7_40_short_cycle_parameter_search.py
reports/v13_7_40_short_cycle_parameter_search_binance_vision_asset_filtered_report.json
reports/v13_7_40_short_cycle_parameter_search_binance_vision_asset_filtered_summary.md
reports/v13_7_40_short_cycle_selected_candidate_cards.json
reports/v13_7_40_short_cycle_selected_candidate_cards.md
docs/V13.7.40-short-cycle-parameter-search-binance-vision-asset-filtered.md
```

Result:

```text
dataCoverage: 44 Binance Vision futures pairs, 1h / 30m / 15m, 2020-2026
candidateCount: 1011
approvedCount: 33
selectedCount: 5
approvedSelectedCount: 5
targetR: 2.0
dryRunApproved: false
liveTradingApproved: false
```

Selected candidates:

```text
1h short rejection ATR1.0 asset-filter Top10
  trades 219, winRate 51.1416%, PF 1.5170, test PF 1.5075, maxDD 10.9678R
1h short rejection ATR1.0 asset-filter Top10
  trades 219, winRate 49.3151%, PF 1.4348, test PF 1.5031, maxDD 11.8513R
1h short rejection ATR1.0 asset-filter Top10
  trades 219, winRate 49.3151%, PF 1.5112, test PF 1.3785, maxDD 11.9660R
1h short rejection ATR1.0 asset-filter Top8
  trades 175, winRate 52.0000%, PF 1.5545, test PF 1.4233, maxDD 9.9030R
1h short rejection ATR1.2 asset-filter Top10
  trades 131, winRate 54.9618%, PF 1.6850, test PF 1.3186, maxDD 7.2055R
```

The asset filter selects pairs from the train split only; validation and test
remain out of selection. These candidates are approved for local sandbox /
paper-observation research only. They are not exchange Dry-run candidates and
not live trading strategies.

V13.7.40 does not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, exchange
Dry-run execution, live trading, or automatic trading.

## V13.11.0 Evolution Registry Foundation

V13.11.0 adds the first foundation of the Factor Evolution Research Kernel: a
local, immutable SQLite registry for data snapshots, factor definitions,
experiments, models, strategy families, promotion decisions, Demo releases,
drift events, audit events, and legacy research evidence.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_evolution_registry_foundation.ps1
```

Current inventory result:

```text
scanned JSON artifacts: 168
registered evidence: 158
invalid non-standard NaN artifacts: 10
legacy strategy evidence with complete rule fields: 1
runnable StrategyCandidates created: 0
DemoReleases created: 0
orders created: 0
```

Top-level array logs are retained as research evidence but cannot be promoted.
Non-standard `NaN` values are rejected and reported instead of being replaced
with fabricated defaults. Legacy evidence still requires a formal contract,
point-in-time validation, semantic/correlation deduplication, purged
walk-forward evaluation, cost stress, and multiple-testing controls.

Key paths:

```text
alphapilot/evolution/registry/
alphapilot/evolution/data_lineage/
alphapilot/evolution/adapters/
alphapilot/reports/generate_evolution_registry_foundation_report.py
reports/evolution_registry_foundation_report.json
docs/V13.11.0-evolution-registry-foundation.md
```

V13.11.0 is research infrastructure only. It does not use or store API keys,
call Trade API or Withdraw API, read exchange accounts, create orders, promote
legacy reports to Demo/live execution, or enable automatic trading.

## V13.12.0 Factor Research Kernel

V13.12.0 adds a restricted data-only factor DSL, point-in-time validation,
purged walk-forward manifests, FDR, Deflated Sharpe probability, PBO-like
selection diagnostics, block bootstrap, cross-dimension stability, and cost /
latency / gap stress helpers.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_factor_research_kernel_baseline.ps1
```

Existing 16-factor compatibility result:

```text
DSL supported: 11
DSL blocked: 5
legacy candidate factors: 0
formal research ready factors: 0
factor values loaded or modified: false
StrategyCandidates created: 0
DemoReleases created: 0
orders created: 0
```

Three EMA formulas remain blocked because `ts_ema` is outside the whitelist;
one formula uses unapproved `abs`; one formula references `btcReturn_12` while
declaring only `btcReturn`. These definitions are reported, not silently fixed.
DSL compatibility alone is not promotion evidence.

Key paths:

```text
alphapilot/evolution/factor_dsl/
alphapilot/evolution/data_lineage/point_in_time_validator.py
alphapilot/evolution/evaluation/
alphapilot/evolution/adapters/legacy_factor_adapter.py
reports/factor_research_kernel_baseline_report.json
docs/V13.12.0-factor-research-kernel.md
```

V13.12.0 adds no API key handling, private exchange access, StrategyCandidate
auto-promotion, Demo/live release, order creation, or automatic trading.

## V13.13.0 Evolution and ML

V13.13.0 adds bounded AST factor generation, semantic and correlation filters,
a research-only Bandit, deterministic Logistic/boosted-stump models, Platt
calibration, immutable shadow model registration, champion/challenger review,
and a complete 2R strategy-candidate contract.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_evolution_cycle.ps1
```

Current cycle result:

```text
safe seed factors: 11
generated Shadow research factors: 48
research allocation units: 96
correlation filter: blocked_missing_factor_values
registered new-kernel FactorRuns: 0
model training: blocked_missing_registered_training_dataset
Models created: 0
StrategyCandidates created: 0
DemoReleases created: 0
orders created: 0
```

No values or labels are invented to force correlation filtering or ML. Model
training requires registered point-in-time FactorRuns and a matching purged
walk-forward manifest. Champion/challenger success can request Shadow only.

Key paths:

```text
alphapilot/evolution/factor_mining/
alphapilot/evolution/models/
alphapilot/evolution/strategies/
alphapilot/evolution/orchestrator.py
reports/evolution_cycle_report.json
docs/V13.13.0-evolution-and-ml.md
```

V13.13.0 does not use or store API keys, call Trade API or Withdraw API, read
private exchange state, create Demo/live releases, create orders, or trade
automatically.

## V13.24.0 Versioned Risk Profiles

V13.24.0 replaces long-term hard-coded capital and position assumptions with
immutable `RiskProfile` versions for Local Forward, OKX Demo, Live Canary, and
future Live Standard operation.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_24_risk_profiles.ps1
```

Profiles include configurable capital, strategy and position counts, order
notional, leverage, per-trade and portfolio risk, symbol/direction/correlation
concentration, daily loss, drawdown, Canary loss, cooldown, fees, slippage, and
allowed strategies. Values remain bounded by a separate code-reviewed
`SafetyEnvelope`; the routine UI cannot raise that envelope. Every change
creates a new checksum-bound version with append-only activation and rollback
history. Existing positions remain attributable to the profile used when they
were opened.

RiskProfile activation does not grant order permission. V13.24.0 stores no raw
API credentials, has no Withdraw support, has no Live exchange adapter, and
keeps Live execution disabled.

## V13.25.0 Fail-Closed OKX Live Canary

V13.25.0 adds an immutable `LiveRelease` registry contract and a fail-closed
OKX Live Canary runtime adapter in the Control Console. A release requires an
approved Live candidate, active checksum-matched Live Canary RiskProfile, and
timestamped manual approval.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_25_live_canary_report.ps1
```

The Live runtime is disabled by default. It requires separate master, read,
Canary, and order process gates, process-only credentials, read-only private
state reconciliation, manual ARM, isolated margin, attached TP/SL, at least 2R,
idempotency, restart recovery, and kill-switch support. Unknown state pauses
new entries. Withdraw is not implemented. The V13.25 report reads no
credentials or private account state and places no order.

## V13.26.0 Formal Execution Outcome Feedback

V13.26.0 closes the evidence path from fully reconciled OKX Demo and Live
Canary trades back into the immutable offline Outcome Ledger.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_26_execution_feedback.ps1
```

The importer verifies the export manifest, every outcome checksum,
DataSnapshot, StrategyCandidate, DemoRelease or LiveRelease, and Live
RiskProfile lineage. Entry fills without confirmed exit evidence, incomplete
records, missing parents, checksum mismatches, and private account values are
quarantined. They are never converted into formal feedback by filling gaps.

Execution feedback is offline only. It may inform bounded Shadow research, but
cannot mutate an online model, replace a running release, create a Demo/Live
release, or create an order. The current report remains
`blocked_no_formal_execution_outcomes` until genuine closed Demo or Live
outcomes exist.

## V13.27.0 Unified Workflow Foundation

V13.27.0 adds the immutable state and audit foundation for one strategy
lifecycle:

```text
Strategy backtest -> Local real-time forward -> OKX Demo -> Live
```

Registry migration v6 adds `StrategyVersions`, `GateProfiles`, `WorkflowRuns`,
`StageEvents`, and `FailureDiagnoses`. Strategy logic and parameters are
immutable: any change creates a challenger version that starts again at
backtesting. User actions may request work but cannot mark a stage passed.
Operational failures may retry the same version; strategy-performance failures
require a changed challenger. Checkpoints, idempotency keys, append-only stage
events, and one-current-stage projections provide restart and audit support.

This release is orchestration infrastructure only. It does not launch a real
backtest worker, create an OKX Demo or Live release, store credentials, place
orders, or enable automatic trading. See
`docs/V13.27.0-unified-workflow-foundation.md`.

## V13.27.1 Strategy Backtest Workflow

V13.27.1 connects the immutable workflow foundation to a real local backtest
worker and a fixed command boundary.

- Every run is bound to a strategy hash, registered point-in-time data,
  walk-forward and locked-OOS manifests, cost assumptions, GateProfile, and a
  target of at least 2R.
- Progress, manifests, results, and failure diagnoses are restart-safe and
  auditable.
- Duplicate active workers fail closed, fixed-output adapters are serialized,
  and pause/cancel stops the local adapter process; recovery must be explicit.
- Operational failures may retry the same version, while a strategy-performance
  failure requires a changed challenger version that restarts at backtesting.
- The Alpha191 observer remains waiting because formal data lineage is not yet
  bound. No missing evidence is replaced with a favorable default.

V13.27.1 adds no exchange request, credential storage, order creation, Demo or
Live release, automatic promotion, or automatic trading. See
`docs/V13.27.1-strategy-backtest-workflow.md`.

## V13.27.1.1 Dual-Data One-Click Backtest

V13.27.1.1 connects the workflow backtest action to two evidence classes under
`D:\Codex-Workspace\回测数据`:

- Existing `5m`, `合约数据`, and `现货数据` files are read-only
  `third_party_unverified` research inputs. They can validate implementation,
  but can never satisfy a formal promotion gate.
- Official OKX public OHLCV and funding data are stored separately under
  `_alphapilot`, checksum-bound, validated, and frozen into immutable formal
  snapshots before a fixed `targetR >= 2` backtest can run.
- The workflow is restart-safe and preserves download, snapshot, manifest, and
  backtest checkpoints. A formal pass may create only an awaiting Local Forward
  run. It cannot enter OKX Demo or Live automatically.
- The PowerShell wrapper resolves Unicode strategy names through the Python CLI
  and remains ASCII-safe for Windows PowerShell 5.

Observed release verification:

- Local research smoke completed over 14 selected assets with
  `formalPromotionEligible=false`; metadata fingerprints for all 12,473 source
  files remained unchanged.
- A bounded BTC/ETH/SOL OKX public integration collected 9/9 OHLCV partitions
  for `5m`, `15m`, and `4h`, plus 3 funding files. All partition SHA-256 values
  verified.
- The bounded integration produced a 12-file immutable snapshot and a 4-fold
  purged walk-forward pack with SOL as the unseen-symbol holdout.
- This bounded pack validates the data pipeline only. Alpha191 has not passed
  the full 2020-2026 dynamic-universe formal backtest and did not enter Local
  Forward.

Run the research-only local smoke:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_27_1_1_dual_backtest.ps1 -StrategyName "Alpha191 加密因子观察策略" -SmokeOnly
```

Omit `-SmokeOnly` only when the strategy's complete official-data contract is
ready. No API key, private exchange endpoint, account state, position state,
order creation, Demo transition, or Live activation is used by this workflow.

## V13.27.1.2 Targeted Strategy Optimization Boundary

V13.27.1.2 adds the immutable data boundary required by the Control Console's
targeted optimization action.

- Workflow projections expose the current strategy definition and parameters
  in a local-only `optimizationContext`.
- A changed canonical strategy creates a child `StrategyVersion`; an optimized
  legacy research strategy is imported with explicit legacy lineage.
- Unchanged parameter sets are rejected. Any `targetR`,
  `targetRMultiple`, or `targetRewardRiskRatio` below `2.0` is rejected.
- Every optimized version starts again at the backtest stage. Existing
  backtest, Local Forward, Demo, and archive evidence remains immutable.

This boundary does not select profitable parameters, mark a strategy passed,
create a Demo release, place an order, store an API key, or enable Live
execution.

## V13.27.13 Short-Cycle Structural Redesign

V13.27.13 replaces eleven terminally weak research versions with six new,
evidence-informed candidates: three on 5m and three on 15m. The redesign adds
trend direction, completed-candle confirmation, volatility-range and volume
filters while preserving the BTC shock guard, `targetR >= 2`, cost stress,
walk-forward evidence, and the existing 2R half-exit plus ATR runner.

The candidates are registered as `backtest / awaiting`; they are not marked as
profitable and cannot bypass Local Forward, OKX Demo, or Live gates. See
`docs/V13.27.13-short-cycle-structural-redesign.md`.

## V13.27.17 Long-Horizon Candidate Pack

V13.27.17 selects five auditable research candidates each for `1h`, `4h`, and
`1d`, while keeping candidate count separate from promotion eligibility.

- `1h`: five lower-rigidity event-window successors use two-of-four optional
  confirmation scoring instead of forcing every RSI, volume, candle, and trend
  check onto the same bar. Direct train, temporal-validation, and symbol-
  holdback evidence currently classifies one as research-eligible, one as
  shadow-only, and three as rejected.
- `4h`: five BTC-bull recovery-reclaim variants pass the current development,
  temporal-validation, and deterministic symbol-holdback research checks. They
  share one correlation group and are not five independent risk sources.
- `1d`: three breakout candidates pass the current research checks; two
  oversold-reclaim variants remain shadow-only because the pre-2025 selection
  sample is too small.
- Every candidate keeps `targetR >= 2R`. Data after 2025-01-01 is reported as
  locked evidence and is not used to select parameters or promotion status.
- The report itself creates no StrategyVersion, Demo Release, Live Release,
  API-key storage, account read, position read, or order.
- A separate idempotent registration command is available only for the seven
  research-eligible event-window definitions whose formal-backtest and frozen-
  forward engines are implemented (`5m`: 2, `15m`: 4, `1h`: 1). The `4h` and
  `1d` research packs remain report-only until a matching low-frequency formal
  workflow adapter exists; they are not mislabeled as executable versions.

Run the reproducible report with:

```powershell
.venv\Scripts\python.exe -m alphapilot.reports.generate_v13_27_17_long_horizon_candidate_pack
.venv\Scripts\python.exe -m alphapilot.reports.generate_v13_27_17_cross_timeframe_candidate_inventory
```

See `docs/V13.27.17-long-horizon-candidate-pack.md` and
`reports/v13_27_17_long_horizon_candidate_pack_summary.md`.

The unified inventory contains exactly five candidates per timeframe across
`5m`, `15m`, `1h`, `4h`, and `1d`: 25 candidates in total, 15 currently
research-eligible, 3 shadow-only, and 7 rejected. Candidate count is not a pass
count. To register only the seven executable research-eligible event-window
versions as immutable `backtest / awaiting` records, run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_v13_27_17_event_window_candidates.ps1
```

Formal workflow verification was also run for the seven executable definitions.
Six short-cycle runs completed and failed the unchanged formal gates; the `1h`
run was checkpoint-paused while building its first 50-member public-data
contract (`1h` signal plus `15m` and `5m` execution data). Four bounded
structural-redesign successors were generated from the failures and also failed,
then stopped at the configured generation boundary. The closest original run,
`15m 假突破弱趋势反转 因子后继 ATR1.2`, retained positive average net R but
still failed profit-factor, drawdown, and cost-stress gates. No version was
forced through, and no Demo or Live release was created.

## V13.27.18 Cross-Timeframe Executable Candidate Pack

V13.27.18 registers an auditable five-candidate research inventory for each of
`5m`, `15m`, `1h`, `4h`, and `1d`. The 25 candidates are executable workflow
definitions, not 25 formal passes.

- Long-horizon signals use event windows and staged confirmation so every
  indicator is not forced to agree on one candle.
- Current development evidence marks 13 definitions research-eligible and 12
  shadow-only. Shadow-only candidates remain comparison records and are not
  promoted by registration.
- `4h` formal validation reuses `15m` execution and `1h` fallback data; `1d`
  reuses `1h` execution and `4h` fallback data.
- The new formal data-plan override is allowlisted and fail-closed. Invalid
  timeframe combinations are rejected.
- Formal public collection now filters OKX `instCategory=1` crypto swaps and
  ranks them by 24-hour quote notional (`last * volCcy24h`). It no longer uses
  an alphabetical pseudo-Top50 or mixes equity/ETF perpetuals into crypto
  research.
- The ranked universe is a collection-time snapshot, not a reconstructed
  historical point-in-time universe. That limitation remains explicit and
  must be covered by separate historical-universe robustness evidence before
  any Live decision.
- `targetR >= 2R`, cost stress, walk-forward, symbol holdback, immutable
  snapshots, and locked-data isolation remain unchanged.
- Research screening creates no Demo or Live release and makes no order.

Generate and register the pack with:

```powershell
.venv\Scripts\python.exe -m alphapilot.reports.generate_v13_27_18_cross_timeframe_candidate_pack
.venv\Scripts\python.exe -m alphapilot.evolution.workflow.cli bootstrap-v13-27-18-cross-timeframe
```

See `docs/V13.27.18-cross-timeframe-executable-candidate-pack.md` and
`reports/v13_27_18_cross_timeframe_candidate_pack_summary.md`.

## Next Versions

- V13.7.2: refresh the runtime contract from newly closed forward local paper samples when enough post-selection candles exist.
- V13.4.28 follow-up: resolve remaining FET/TON OHLCV coverage policy before strategy specification.
- V13.5.24: rerun forward readiness after 2026-07-09T20:13:33Z and, if ready, run forward local paper refresh for the V13.5.7 4h alpha overlay.
- V13.5.25: compare V13.5.21 local paper package against newly closed forward samples and flag any drift.
- V13.5.26: consider exchange Dry-run review only after local paper validation and exchange balance are fresh, broad, and manually reviewed.
- V13.6: consider exchange Dry-run candidate evaluation only after local paper validation is fresh, stable, broad, and reviewed.
