# V13.4.11 Next-Step Options

## Implementation Update

V13.4.11 has now implemented the recommended path:

```text
Execution Reality and Liquidity Gate Design
```

The implemented version adds research-only liquidity, slippage, order impact,
shadow trading schema, and live feasibility score modules. It keeps:

```text
dryRunApproved = false
liveTradingApproved = false
```

The next recommended version is:

```text
V13.4.12 - Shadow Trading Skeleton
```

V13.4.10 recommends that the next version should not enter Dry-run and should
not rush into another strategy implementation. The current priority is deciding
how to rebuild the research gate.

## Recommended Path

```text
V13.4.11 - Execution Reality and Liquidity Gate Design
```

Reason:

```text
V13.4.9 raw result was already negative.
Slippage-adjusted result was much worse.
The strategy produced 472 trades and had weak edge per trade.
User concern: backtest profit does not guarantee executable performance.
```

This path designs the filters needed before future candidates can be trusted.

## Option A - Pair Universe Narrowing Validation

Goal:

```text
Test whether the Trend Pullback pattern only makes sense on BTC/ETH/SOL or a
high-liquidity subset.
```

Why it matters:

```text
Top30 expansion failed broadly, while the original BTC/ETH/SOL smoke sample was positive.
```

Risk:

```text
May overfit to a small universe and still fail out of sample.
```

## Option B - Execution Reality and Liquidity Gate Design

Goal:

```text
Define minimum liquidity, volume, notional, and slippage assumptions before any
strategy can pass research gates.
```

Candidate gates:

```text
minimum 24h volume
minimum recent 1h volume
maximum position notional / volume ratio
pair liquidity score
slippage stress test
future orderbook depth support
```

This is the recommended next step.

## Option C - Signal Score Gate Specification

Goal:

```text
Replace binary entry conditions with a score-based research gate.
```

Candidate factors:

```text
4h trend strength
1h pullback quality
volume quality
risk distance
pair liquidity
BTC/ETH market safety
ATR quality
```

Risk:

```text
Weights can become subjective and overfit without strict validation.
```

## Option D - Breakout Retest Strategy Specification

Goal:

```text
Pause Trend Pullback and move to a different V03/V04 strategy direction.
```

Reason:

```text
Trend Pullback failed expanded validation too severely to keep scaling now.
```

Risk:

```text
Requires a new strategy cycle and full validation from smoke to expanded test.
```

## Safety

None of these options approve Dry-run or live trading. They are research design
paths only.
