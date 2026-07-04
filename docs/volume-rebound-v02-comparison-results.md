# Volume Rebound V0.2 Comparison Results

This document summarizes the V13.4.4 smoke comparison. It is not a Dry-run
approval.

## Comparison Table

| Strategy | Return % | Drawdown % | Profit Factor | Trades | Win Rate % | Max Loss Streak | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| V0.1 Baseline | -15.542 | 24.4939 | 0.8107 | 230 | 41.3043 | 13 | false |
| V0.2A Trend Strict | -11.6607 | 21.0664 | 0.8251 | 179 | 41.3408 | 10 | true |
| V0.2B Volume Quality | -4.0845 | 11.4841 | 0.9104 | 116 | 45.6897 | 9 | true |
| V0.2C Exit Cleanup | -6.1609 | 17.8594 | 0.9319 | 220 | 51.3636 | 10 | true |
| V0.2D Early Failure Exit | -15.6258 | 24.3002 | 0.7979 | 231 | 36.7965 | 13 | false |
| V0.2E Pair Risk Watchlist | -10.3361 | 17.93 | 0.8406 | 182 | 40.6593 | 10 | true |

## Candidate Notes

### V0.2A Trend Strict

The stricter 4h trend gate improved return, drawdown, profit factor, trade
count, and loss streak versus baseline, but total return remains negative.

### V0.2B Volume Quality

The stricter volume threshold produced the best total return and drawdown in
this smoke comparison. It reduced trades from 230 to 116, but still ended
negative.

### V0.2C Exit Cleanup

The MACD profit-only cleanup produced the best profit factor and win rate.
However, stop-loss loss increased, so this candidate needs careful follow-up.

### V0.2D Early Failure Exit

The six-candle no-profit exit did not improve the comparison gate. It had worse
return and profit factor than baseline.

### V0.2E Pair Risk Watchlist

The SOL daily cap reduced SOL exposure and improved drawdown versus baseline,
but the result is still negative and must not be treated as proof that SOL
should be excluded.

## Dry-run Decision

```text
dryRunApproved = false
```

All candidates remain negative in the smoke sample, and slippage is not applied
by the Freqtrade command. Longer-range validation is required before any
controlled execution discussion.

## V13.4.6 Follow-up

After V13.4.5 expanded validation with slippage, the V0.1/V0.2 family is
rejected for Dry-run. B/C/E were useful diagnostic comparisons, but they should
not be micro-tuned further as the next step. V13.4.6 moves the research program
to V03 redesign.
