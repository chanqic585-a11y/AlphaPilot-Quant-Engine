# AlphaPilot V13.16-V13.22 Data-to-Live Evidence Pipeline

## Status

Approved by the user on 2026-07-10. The selected approach is data-first staged automation. Candidate strategies must target a reward/risk ratio of at least `2R`.

## Goal

Build one auditable pipeline from local historical market data to automatic research, historical replay, real-time local forward observation, OKX Demo validation, Live Candidate review, and offline strategy evolution.

The pipeline must maximize reproducibility and bounded risk. It must not describe historical replay, synthetic samples, or Demo results as live performance, and it must not promise profitability.

## Fixed Product Boundary

```text
Historical and public market data
  -> immutable point-in-time DataSnapshot
  -> FactorRun and labels
  -> purged walk-forward research
  -> StrategyCandidate
  -> historical path replay
  -> real-time local forward observation
  -> immutable DemoRelease
  -> OKX Demo execution and outcome ledger
  -> LiveCandidatePackage
  -> one user approval per Live Release
  -> mechanical execution inside a fixed risk envelope
```

ML and factor mining may propose challengers. They may not edit a running model, approve a Live Release, change the live risk envelope, or bypass any validation stage.

## Repository Responsibilities

### AlphaPilot-Quant-Engine

- Owns raw-data catalogs, canonical market data, immutable snapshots, FactorRuns, labels, experiments, models, strategy candidates, historical replay, promotion evidence, Demo releases, Live Candidate packages, and offline champion/challenger evaluation.
- Produces versioned JSON contracts for the console and mobile app.
- Never stores API credentials and never creates exchange orders.

### AlphaPilot-Control-Console

- Consumes immutable releases and evidence contracts.
- Runs real-time local forward observation and OKX Demo control.
- Owns execution arbitration, risk gates, idempotency, reconciliation, automatic pause, rollback, and operator-facing reports.
- Does not invent research evidence or promote a strategy that has no immutable release.

### trade-discipline-journal

- Displays compact strategy, local-forward, Demo, and Live Candidate status.
- Allows the user to approve or revoke a Live Release.
- Does not train models, store raw API credentials, or place orders directly.

### AlphaPilot-Docs

- Stores version prompts, architecture decisions, operational runbooks, and safety boundaries.

## Storage Design

The existing `D:\Codex-Workspace\回测数据` directory remains the immutable raw-data source. Existing files are not moved, rewritten, or silently deleted.

Canonical outputs live under:

```text
AlphaPilot-Quant-Engine/data/market/
  catalog/
  canonical/
  snapshots/
  checkpoints/
  quarantine/
```

Registry metadata remains in `data/evolution_registry.sqlite`. Large canonical tables use Parquet or Feather. JSON is a report and contract format, not the primary analytical store.

Docker mounts the raw directory read-only and canonical/output directories explicitly. The Docker container is never the only copy of market data.

## V13.16 Data Foundation

### Raw Catalog

Every discovered source file receives a catalog record containing:

- relative source path;
- file size and SHA-256;
- market type, instrument, timeframe, year, and source format;
- inferred exchange and confidence of that inference;
- provenance status, license status, download time when known;
- first and last timestamp when inspected;
- row count when inspected;
- duplicate family, checkpoint, unconfirmed-tail, and quarantine flags.

The catalog must not claim OKX provenance solely because columns resemble OKX. Unknown provenance remains explicitly unknown.

### Canonicalization Rules

- UTC milliseconds are the canonical time key.
- User-facing Beijing time is derived only at presentation time.
- Prefer `timestamp_ms`; Excel serial `utc_time` is a fallback converted with the Excel epoch.
- Keep only confirmed candles.
- Deduplicate by exchange, market type, instrument, timeframe, and opening timestamp.
- Annual files and `_ALL` files are one duplicate family. The canonicalizer selects one source policy and never imports both.
- `*_CKPT.csv`, timestamped duplicate exports, malformed files, and ambiguous files are quarantined or explicitly excluded.
- OHLC values must be finite and satisfy `low <= open/close <= high`.
- Volume must be non-negative.
- Missing intervals are reported, never silently forward-filled in raw or canonical OHLCV.
- Output writes use a temporary file followed by atomic rename.

### Incremental Public Data

The incremental collector may use public endpoints only to fill the range after the last confirmed local candle. It records source URL family, request window, collected time, response status, and checksums. It respects exchange rate limits and never requests account or order endpoints.

### Point-in-Time Snapshot

A DataSnapshot contains exact canonical files, hashes, universe membership at cutoff, start/end times, data-quality report, and a point-in-time cutoff. A snapshot is immutable after registration.

### V13.16 Exit Gate

- All raw files are cataloged or explicitly failed.
- Known duplicate and checkpoint patterns are classified.
- No unconfirmed candle enters canonical output.
- At least BTC, ETH, and SOL smoke snapshots pass timestamp, OHLCV, gap, and hash verification.
- Interrupted catalog or conversion runs resume without reprocessing completed files.

## V13.17 FactorRun and Automatic Backtest

### Feature Matrix

The initial materialized matrix includes only point-in-time values available at each bar close. It may include returns, volatility, trend, RSI, MACD histogram, Bollinger position, volume ratios, funding, open interest, BTC regime context, and approved Alpha101/Alpha191-safe expressions.

Every factor column maps to a registered FactorDefinition and completed FactorRun. A FactorRun records DataSnapshot ID, code commit, configuration hash, result path, result hash, coverage, null rate, and point-in-time validation.

### Labels

The default directional label uses:

- signal decision at completed bar `t`;
- entry at the next eligible bar, never at the already-known close;
- stop distance equal to `1R`;
- target distance at least `2R`;
- explicit maximum holding window;
- fees, funding, and slippage included in net outcome;
- conservative stop-first outcome when both target and stop are touched in the same OHLC bar and no lower timeframe can resolve the order.

Strategies may use targets greater than `2R`; none may reduce the configured target below `2R` merely to increase win rate.

### Evaluation

- Expanding or rolling purged walk-forward with embargo.
- At least three valid OOS folds.
- Locked final test unavailable during parameter search.
- Baseline, 2x cost, 3x cost, and one-bar-delay stress.
- Pair, month, exchange, and market-regime decomposition.
- Multiple-testing control, parameter-neighborhood stability, and concentration checks.
- No random train/test split for time-series evidence.

### Strategy Candidate

A formal StrategyCandidate is created only from registered DataSnapshots, FactorRuns, Experiment, optional Model, locked strategy parameters, cost model, and reproducible backtest evidence. A candidate remains research-only until subsequent gates pass.

## V13.18 Historical Path Replay

The current synthetic local sandbox is retained only as `legacy_synthetic` evidence and excluded from training, profitability claims, and promotion.

The replacement replay engine uses actual canonical bars and an event-time clock:

- signal evaluation at bar close;
- next-bar fill with configured slippage;
- persistent open-position state;
- intrabar target/stop handling with conservative ambiguity rules;
- fees, funding, margin, and mark-to-market accounting;
- MFE, MAE, holding time, exit reason, and execution-quality fields;
- deterministic replay from the same snapshot and release;
- one immutable Outcome Ledger event for every signal, rejection, fill, update, exit, and error.

Historical replay uses frozen holdout windows not used for fitting the candidate.

## V13.19 Real-Time Local Forward Observation

The local forward runner consumes public real-time data after a release is frozen. Time cannot be accelerated. It creates no exchange order and uses a 1000 USDT virtual account per configured test account.

Historical replay and forward records use different evidence classes. Downtime is recorded as a collection gap. Missing order-book state, latency, or no-trade decisions cannot be reconstructed and must not be backfilled as forward evidence.

## V13.20 OKX Demo

Only an immutable DemoRelease may activate Demo automation. A release contains strategy/model/data hashes, eligible instrument policy, a 1000 USDT risk envelope, rollback target, and safety checks.

The console performs public-market scanning, strategy arbitration, liquidity and data gates, Demo order lifecycle, protective exits, reconciliation, drift evaluation, and automatic pause. Runtime credentials remain process-only; Withdraw and Live remain locked.

Demo reports include strategy and release identity, signals and rejections, K-line context, orders, fills, positions, fees, funding, slippage, latency, PnL attribution, drawdown, drift, reconciliation, and promotion readiness.

## V13.21 Live Safety Candidate

Demo evidence may produce a LiveCandidatePackage, never automatic live permission. Live readiness requires immutable checksums, sufficient calendar and closed-sample coverage, net performance after costs, bounded drawdown, no unresolved critical drift, reproducible outcome manifests, and a rollback plan.

The live safety plane is implemented and tested in disabled mode first. It includes credential isolation, private WebSocket state, client-order idempotency, request expiry, price-limit and instrument-state checks, account reconciliation, restart recovery, circuit breakers, and kill switch.

Actual Live activation requires one explicit user approval for the exact release and risk envelope. Any strategy, model, universe, leverage, or risk-budget change creates a new approval request.

## V13.22 Offline Evolution Loop

Outcome Ledger data from replay, local forward, Demo, and eventual Live are separate datasets with explicit evidence classes. Offline jobs may diagnose failure modes, materialize new FactorRuns, train challengers, and generate new StrategyCandidates.

The running champion is immutable. A challenger must repeat the complete OOS, replay, forward, and Demo path. AI summaries and multi-agent research may explain or prioritize experiments but never produce executable code without validation and never receive execution authority.

## Checkpoint and Resume

- Every batch run has a manifest and stable run ID.
- Each source file, symbol/timeframe, fold, strategy, and replay window has an independent status.
- Completed units are skipped on resume unless their hash changed.
- Failed units retain error details and may be retried independently.
- Partial outputs use temporary names and do not replace valid outputs.
- Startup recovery verifies git state, registry migrations, output hashes, active Docker containers, and stale locks before resuming.

If Codex usage limits stop work, no background coding continues. The same task resumes from committed phases and manifests after usage becomes available. Sudden shutdown may lose only the currently uncommitted unit; forward/Demo market conditions missed during downtime are recorded as gaps rather than fabricated.

## UI Contract

One strategy appears in one current lifecycle stage. Strategy, local replay, local forward, Demo, and Live pages consume stable contracts and do not duplicate the same candidate under different labels.

The UI distinguishes:

- historical backtest;
- historical path replay;
- real-time local forward;
- OKX Demo;
- Live Candidate;
- approved Live Release.

Legacy synthetic samples are hidden from primary performance totals and remain accessible only in research archive/audit views.

## Safety Rules

- No Withdraw API.
- No raw API key in Git, SQLite, browser storage, logs, reports, or chat.
- No automatic Live approval.
- No online mutation of a running model.
- No use of future bars or random time-series splits.
- No fabricated missing data or synthetic sample presented as forward evidence.
- No profitability guarantee.

## Verification

Each phase must pass its unit and integration tests, Python compileall, configuration validation, safety scan, report-schema checks, reproducibility checks, and `git diff --check`. Data-heavy jobs must produce compact reports and resumable manifests.

## Completion Definition

Engineering completion means all modules, contracts, tests, runbooks, and disabled safety paths are implemented and the offline smoke pipeline runs end to end. Strategy validation completion remains time-dependent: local forward and OKX Demo evidence must accrue over the required real calendar window before any Live Candidate can pass.
