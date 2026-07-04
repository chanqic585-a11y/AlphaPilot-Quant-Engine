# Trend Pullback 1H Expanded Results

This page summarizes the V13.4.9 expanded validation for:

```text
AlphaPilotTrendPullback1HV01
alpha_trend_pullback_1h_v01
```

## Research Decision

```text
Decision: rejected for Dry-run
Reason: expanded Top30 validation failed after raw and slippage-adjusted checks
Next: V13.4.10 Trend Pullback Redesign Review
```

The strategy remains a research artifact only.

## Why V13.4.8 Was Not Enough

V13.4.8 passed a small BTC/ETH/SOL smoke sample:

```text
tradeCount = 61
totalReturnPct = +6.6227
maxDrawdownPct = 9.8727
profitFactor = 1.1933
```

That result was useful for verifying implementation and runtime behavior. It
was not enough to approve Dry-run.

V13.4.9 expanded the same strategy to a requested fixed Top30 sample:

```text
requestedPairCount = 30
supportedPairCount = 28
timerange = 20260101-
timeframe = 1h
tradeCount = 472
```

The expanded result failed:

```text
rawTotalReturnPct = -61.0503
rawProfitFactor = 0.7067
rawMaxDrawdownPct = 67.296
slippageAdjustedTotalReturnPct = -113.218
slippageAdjustedProfitFactor = 0.5361
slippageAdjustedMaxDrawdownPct = 112.2244
```

## Interpretation

The expanded sample shows that the Trend Pullback 1H V0.1 logic is too weak for
the current Top30 futures universe. The positive ETH/SOL slices did not survive
broader pair and month exposure.

Useful lessons:

- The entry pattern can work on isolated pairs.
- The current filters do not control enough broad-market downside.
- Stop losses dominate too often in expanded conditions.
- Cost sensitivity is severe once slippage is modeled.
- The strategy needs redesign before another Dry-run discussion.

## V13.4.10 Direction

V13.4.10 should not be simple parameter tuning. It should review the strategy
direction and decide whether to:

- require stronger market regime filters;
- reduce trade frequency materially;
- add pair-specific exclusion or scoring;
- add better reward/risk structure;
- redesign the pullback confirmation logic;
- or retire this branch and test a different V03 candidate.

## Safety

This result is not a live signal and not a trading recommendation. AlphaPilot did
not use exchange credentials, did not call Trade API or Withdraw API, did not
read accounts or positions, did not create orders, and did not auto trade.

