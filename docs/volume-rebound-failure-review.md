# Volume Rebound Failure Review

This document records why the current Volume Rebound V0.1/V0.2 strategy family
is rejected for Dry-run after V13.4.5.

## Expanded Validation Result

Raw Top30 six-month validation:

| Strategy | Return % | Drawdown % | Profit Factor | Trades |
|---|---:|---:|---:|---:|
| V01 | -99.2732 | 99.3724 | 0.6689 | 2701 |
| V02B | -94.1710 | 94.7185 | 0.6152 | 1515 |
| V02C | -99.1303 | 99.2719 | 0.6739 | 2496 |
| V02E | -99.3093 | 99.3953 | 0.6637 | 2671 |

Slippage-adjusted validation:

| Strategy | Adjusted Return % | Adjusted PF | Trades |
|---|---:|---:|---:|
| V01 | -193.4577 | 0.4603 | 2701 |
| V02B | -168.5489 | 0.4225 | 1515 |
| V02C | -187.2377 | 0.4726 | 2496 |
| V02E | -191.7425 | 0.4569 | 2671 |

## Failure Reasons

### Trade Frequency

V01, V02C, and V02E generate roughly 2,500-2,700 trades on the Top30 six-month
sample. V02B reduces trade count to 1,515, but it is still deeply negative after
slippage. The 15m signal density is too noisy for the current edge.

### Cost Sensitivity

Every candidate becomes worse after slippage post-processing. The strategy
family is cost-sensitive because it trades often while edge per trade is weak.
V03 must reduce trade frequency, improve expectancy, or both.

### Payoff Structure

The current -3% stoploss and +3% take-profit shape is roughly 1:1. With win rate
around the low-40% range in key samples, that structure is not enough after fees
and slippage. V03 should test at least 1.5R or 2R concepts.

### Entry Quality

The current volumeRatio, RSI, MACD, EMA20 reclaim, and broad 4h filter
combination does not identify positive-expectancy entries. The failure is
structural, not a single threshold issue.

### Trend Filter

V13.4.2 shows `weak_4h_trend` is the largest skip reason, so the 4h trend filter
has value. However, trades that pass the current filter still lose overall. V03
cannot rely on 4h EMA filtering alone.

### SOL / Pair Risk

V13.4.1 and V13.4.2 show SOL contributed a large portion of smoke-sample loss
and had many final entries. This shows pair-level risk matters. It does not
justify permanently excluding SOL from one sample. V03 should include pair-level
exposure caps, signal caps, and risk watchlists.

## Decision

```text
dryRunApproved = false
strategyFamilyStatus = rejected_for_dry_run
```

Do not continue minor B/C/E threshold edits as the next step. Move to V03
direction selection and specification.

