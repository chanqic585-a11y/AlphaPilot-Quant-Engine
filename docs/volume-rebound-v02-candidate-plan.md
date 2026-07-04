# Volume Rebound V0.2 Candidate Plan

This plan describes how V13.4.4 should compare the V13.4.3 candidates. It is
not a Dry-run approval and not a live-trading plan.

## Baseline

Keep V0.1 unchanged as the baseline:

```text
Strategy: AlphaPilotVolumeReboundV01
Timerange: same V13.4 smoke range first
Pairs: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
```

## Candidate Variants

### V0.2A Trend Strict

Test stricter 4h trend gates:

- `close_4h >= ema200_4h`
- optional `ema20_4h >= ema200_4h`
- optional non-negative 4h EMA20 slope

### V0.2B Volume Quality

Test stronger volume quality:

- `volumeRatio >= 2.0`
- non-isolated volume spike check
- candle body quality check

### V0.2C Exit Cleanup

Test MACD weakness exit variants:

- MACD weakness exit only when trade profit is positive
- remove MACD weakness exit for comparison
- require MACD weakness plus `close < EMA20`

### V0.2D Early Failure Exit

Test earlier failure detection:

- no profit after 4 closed 15m candles
- no profit after 6 closed 15m candles
- replace 12-candle no-profit time stop with 8 closed 15m candles

### V0.2E Pair Risk Watchlist

Test pair-level risk controls:

- pair-level cooldown after loss streak
- max trades per pair per day
- pair-level risk cap
- no permanent SOL removal

## Metrics

Every comparison report should include:

- total return
- max drawdown
- profit factor
- trade count
- win rate
- max consecutive losses
- pair performance
- monthly performance
- stop-loss net loss
- MACD weakness exit net loss
- fees
- slippage-adjusted net return

## Passing Principle

A candidate should not pass only because it has the highest return. It must also
show acceptable drawdown, profit factor, loss streak, and pair/month stability.

## Guardrails

- Do not enter Dry-run in V13.4.4.
- Do not trade live.
- Do not permanently remove SOL based on one smoke range.
- Do not change V0.1 baseline.
- Do not approve a candidate without fee and slippage review.

## V13.4.4 Result Follow-up

V13.4.4 executed the first smoke comparison for V0.1 and V0.2A/B/C/D/E.

Summary:

```text
V0.1 baseline: -15.542% return, 24.4939% drawdown, 0.8107 profit factor
V0.2A: -11.6607% return, 21.0664% drawdown, 0.8251 profit factor
V0.2B: -4.0845% return, 11.4841% drawdown, 0.9104 profit factor
V0.2C: -6.1609% return, 17.8594% drawdown, 0.9319 profit factor
V0.2D: -15.6258% return, 24.3002% drawdown, 0.7979 profit factor
V0.2E: -10.3361% return, 17.93% drawdown, 0.8406 profit factor
```

V0.2B, V0.2C, and V0.2E are the most useful follow-up candidates, but all
remain negative in this smoke sample. Dry-run remains blocked.
