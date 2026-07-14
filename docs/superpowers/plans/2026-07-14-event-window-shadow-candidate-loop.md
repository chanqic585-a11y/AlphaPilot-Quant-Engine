# Event-Window Candidate And Shadow Research Implementation Plan

**Goal:** Register and continuously test five evidence-informed 5m and five
15m candidates without weakening formal promotion gates.

## Task 1: Lock behavioral tests

- Add candidate-catalog tests for count, diversity, 2R, event windows, and
  archived-failure lesson metadata.
- Add signal tests proving a setup can precede confirmation by two or three
  closed candles and that stale setups do not trigger.
- Add shadow-observation tests for one/two failed checks and zero execution.
- Add pre-screen tests for weak-candidate rejection and diverse top-five
  selection.
- Add bootstrap/CLI idempotency tests.

## Task 2: Implement event-window signals

- Add five allowlisted event-window signal families.
- Keep current candle as the only signal candle.
- Reuse existing indicators, BTC shock guard, ATR range, and cost model.
- Expose named check masks for shadow diagnostics without changing existing
  `build_signal` callers.

## Task 3: Implement development pre-screen

- Load only the latest canonical public OHLCV partition per selected symbol.
- Restrict the pre-screen to a declared early development interval.
- Simulate fixed 2R exits with fee and slippage.
- Save a deterministic JSON report with all results and selection reasons.
- Select exactly five candidates per timeframe with family-diversity limits.

## Task 4: Register and queue candidates

- Add an idempotent bootstrap command for the selected pack.
- Store pre-screen report hash and failure lessons in immutable definitions.
- Back up and integrity-check the registry.
- Register ten awaiting backtest versions and queue them in the existing serial
  worker.

## Task 5: Validate and operate

- Run focused tests, then `pytest tests`.
- Run configuration and safety checks.
- Confirm no Demo/Live release changed.
- Commit and push the research implementation.
- Monitor formal results; allow only bounded optimization/structural redesign.
- Continue with new evidence-informed versions until one passes or the user
  requests a pause, without forcing promotion.
