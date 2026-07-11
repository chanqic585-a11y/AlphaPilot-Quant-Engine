# V13.27.4 Workflow Pause, Queue, and Demo Release Design

## Goal

Make the strategy workflow operationally truthful and easy to control: pause must stop the real worker, selected runs must all enter a visible serial queue, formal passes must automatically begin local forward observation, and a user may explicitly release a formally backtested strategy to OKX Demo without pretending missing local-forward evidence exists.

## Approved Product Semantics

- Formal backtests remain historical point-in-time dynamic Top50 tests with target reward/risk at or above 2R.
- `Pause` is complete only after the active worker stops consuming data and releases its run lock. Existing checkpoints remain restartable.
- `Start selected` queues every eligible selected run immediately, but one heavy backtest worker executes them in caller order.
- Console restart recovers queued/running backtests as one serial batch, never as many competing workers.
- A formal backtest pass already creates the local-forward release and executes the first public-market cycle. V13.27.4 preserves and exposes this automatic behavior.
- Local forward keeps collecting real completed-candle evidence. It is never marked passed merely because a user overrides it.
- A local-forward card gains `人工放行到 Demo`. The existing audited Demo override requires a reason, exact confirmation, a formal backtest with trades, a complete strategy definition, target R at least 2, and an active versioned OKX Demo RiskProfile.
- The override records missing local-forward evidence and creates only an immutable OKX Demo release. It creates no order itself.
- OKX Demo is the final strategy-performance gate for an overridden strategy. Once complete Demo evidence passes, missing local-forward evidence does not independently block Live Candidate review.
- Pre-Demo direct live promotion remains forbidden. Live credentials, immutable release identity, risk profile, per-process ARM, reconciliation, TP/SL, circuit breakers, and emergency stop remain separate runtime gates.

## Architecture

### Quant Engine

1. `OkxPublicClient.history_candles` receives an optional stop callback and checks it before every public-history page.
2. `OkxOfficialHistoryCollector` combines its existing pause marker with a workflow-status callback. A stop interrupts the current partition without writing partial data.
3. `workflow_worker_lock` supports bounded waiting for resume. A resumed child keeps the run paused while the old worker exits, then acquires the lock and continues from persisted checkpoints.
4. `run-selected-backtests` validates the full selection, queues every run first, then executes the queued runs serially.
5. Local-forward results retain `strategyCandidateId` so Console controls use immutable identity rather than name matching.

### Control Console

1. Startup recovery groups incomplete backtests into one serial worker.
2. Strategy cards show all selected runs as queued immediately while one card shows active progress.
3. Local-forward cards expose the existing audited Demo override dialog by immutable candidate ID.
4. Override contracts record `postDemoPromotionPolicy=demo_validation_supersedes_local_forward_evidence`. The contract remains Demo-only until complete Demo validation.
5. User-facing status explains that artificial forward release does not equal forward evidence and that Demo must still pass.

## Failure Handling

- Stop callbacks raise a dedicated interruption, not a generic collection failure; the workflow remains paused rather than blocked.
- If a resume cannot acquire the old lock within the bounded wait, the worker returns the current state and the UI reports that shutdown is still in progress.
- Batch validation is all-or-nothing before queueing. Duplicate or ineligible IDs are rejected without partially queueing the selection.
- A failed Demo override writes no release and creates no order.

## Verification

- Unit tests reproduce page-level collection interruption, lock handoff, queue-all-before-first-run, serial startup recovery, local-forward candidate identity, and local-page Demo override controls.
- Full Quant and Console test suites, compile checks, Node syntax, `git diff --check`, targeted safety scan, and live API status checks must pass.
- Production registry is backed up before restarting the paused runs.
