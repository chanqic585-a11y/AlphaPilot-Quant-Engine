# Trend Pullback Expanded Failure Analysis

This analysis explains why the V13.4.8 Trend Pullback 1H smoke success should
not be treated as strategy approval.

## What Worked In The Smoke Test

The V13.4.8 smoke test validated implementation mechanics:

```text
BTC/ETH/SOL only
61 trades
+6.6227% total return
1.1933 profit factor
9.8727% max drawdown
```

That was enough to prove the strategy file could run and produce a positive
small-sample checkpoint. It was not enough to prove robustness.

## What Failed In Expanded Validation

V13.4.9 expanded the same logic:

```text
fixed Top30 requested
28 supported pairs
472 trades
-61.0503% raw return
-113.218% slippage-adjusted return
0.5361 slippage-adjusted profit factor
112.2244% slippage-adjusted max drawdown
```

The failure came from a combination of wider universe exposure, longer time
coverage, weak signal quality, and cost sensitivity.

## Pair-Level Lesson

ETH and SOL were still among the better raw pairs, while BTC became a major
loss pair in the expanded sample. Other Top30 pairs contributed most of the
slippage-adjusted loss:

```text
BTC/ETH/SOL adjusted total profit abs = -68.7442361
Other pairs adjusted total profit abs = -1063.43621155
```

This supports testing a narrower universe later, but it does not prove that
BTC/ETH/SOL alone is safe. The sample could overfit to the smoke window.

## Monthly / Regime Lesson

Losses appeared across multiple months:

```text
January 2026
March 2026
April 2026
May 2026
```

The largest raw loss months were January, April, and May. The strategy likely
needs a stronger market regime filter rather than more simple entry threshold
tuning.

## Execution Reality Lesson

The strategy was already negative before slippage. Slippage made it much worse:

```text
rawTotalReturnPct = -61.0503
slippageAdjustedTotalReturnPct = -113.218
slippageCost = 521.67704423
```

This validates the user's concern that backtest profitability is not the same
as executable profitability. Any future candidate must model liquidity and
execution reality earlier.

## Recommendation

Do not continue by making small parameter edits to the same rule set. The next
work should prioritize execution reality, liquidity gates, market regime
classification, and signal scoring before another strategy implementation.

