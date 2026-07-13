# Formal Backtest Performance Design

## Goal

Reduce AlphaPilot formal backtest time without changing signal generation, entry/exit rules, costs, funding, splits, or reported trade results.

## Decision

Two approaches were considered:

1. Micro-optimize the current pandas-per-signal implementation. This is low-touch but retains repeated full-frame copies, sorting, coercion, filtering, and regime scans, so it cannot reliably solve multi-hour runs.
2. Prepare each instrument once as validated, sorted numeric arrays and use binary search to locate each signal's execution window. This removes repeated frame work while preserving the current candle-by-candle exit loop and formulas.

Use approach 2. Prepared data is immutable for a run and cached per instrument. Baseline and stress evaluations share the same prepared path. Regime labels use a prepared timestamp array plus binary search.

## Boundaries

- Do not change strategy definitions or generated signals.
- Do not change the conservative both-hit rule, gap handling, fee, slippage, funding, MFE, MAE, or net-R formulas.
- Do not change snapshot eligibility, Walk-forward, holdout, or locked-OOS rules.
- Do not add dependencies.
- A legacy DataFrame entry point remains available for compatibility.

## Interfaces

- `prepare_fixed_r_execution_path(executionFrame, fundingFrame=None)` validates and converts one instrument into `PreparedFixedRExecutionPath`.
- `evaluate_prepared_fixed_r_path(..., preparedPath, config)` performs the same evaluation against the prepared arrays.
- `evaluate_fixed_r_path(...)` becomes a compatibility wrapper that prepares and evaluates once.
- `run_formal_strategy_backtest(...)` prepares execution and funding data lazily once per instrument and reuses it for baseline and stress.
- A prepared regime lookup maps timestamps through `numpy.searchsorted` instead of slicing a pandas Series for each trade.

## Verification

1. Test-first parity cases cover long, short, stop, target, both-hit, gaps, timed exit, latency, funding, and stress.
2. A deterministic randomized parity test compares every result field between the compatibility path and prepared path.
3. An integration test proves formal backtest preparation occurs once per instrument rather than twice per accepted signal.
4. A benchmark fixture records old-style compatibility timing versus one-time preparation plus repeated evaluation. The optimized path must be materially faster without asserting fragile wall-clock production estimates.
5. Existing evolution tests, compileall, config validation, safety scan, and `git diff --check` must pass.

## Operational Rollout

Resume only one paused formal run after verification. Confirm result creation and elapsed time before allowing the persistent queue to continue. Do not claim that all ten runs will finish until measured throughput exists.
