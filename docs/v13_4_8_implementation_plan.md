# V13.4.8 Implementation Plan

Proposed next version:

```text
V13.4.8 - Implement Trend Pullback 1H V03 Strategy and Smoke Backtest
```

V13.4.8 is the first version that may implement strategy code for the selected
V03 direction. It still must not enter Dry-run or live trading.

## Scope

1. Add `user_data/strategies/AlphaPilotTrendPullback1HV01.py`.
2. Do not modify old VolumeRebound strategies.
3. Implement 1h trend pullback entry logic from the V13.4.7 spec.
4. Implement ExitProfileA first.
5. Run BTC / ETH / SOL smoke backtest.
6. If smoke runs without runtime errors, run fixed Top30 six-month validation.
7. Generate slippage-adjusted AlphaPilot report.
8. Keep `dryRunApproved=false` unless quality gates are met in a later review.

## Implementation Order

### Step 1 - Strategy Skeleton

Create a new Freqtrade strategy file with a distinct class name:

```text
AlphaPilotTrendPullback1HV01
```

Keep V01/V02 files unchanged.

### Step 2 - Indicators

Implement:

- 1h EMA20 / EMA50 / EMA200
- 4h EMA20 / EMA50 / EMA200
- RSI14
- MACD histogram
- volumeRatio
- ATR or ATR% if feasible
- BTC 1h / 4h informative context

### Step 3 - Entry Logic

Implement the V13.4.7 filters:

- 4h trend filter
- BTC market safety filter
- 1h pullback location
- reclaim / confirmation
- volume quality
- no-chase filter

Risk quality can be optional in the first implementation if it would slow down
the smoke test.

### Step 4 - ExitProfileA

Implement:

- stoploss `-2.5%`
- take profit `+5%`
- 8-hour non-profitable time stop
- profit-only momentum exit if included

### Step 5 - Smoke Backtest

Run BTC / ETH / SOL first. Confirm the strategy has no runtime errors before
expanding the universe.

### Step 6 - Top30 Validation

Run fixed Top30 six-month validation only after smoke succeeds.

### Step 7 - Report

Generate a versioned AlphaPilot report with slippage-adjusted metrics and an
explicit `dryRunApproved=false` unless every quality gate is met and separately
reviewed.

## Safety

V13.4.8 still must not use real API keys, call Trade API or Withdraw API, read
real accounts or positions, create real orders, enter Dry-run, or auto trade.

