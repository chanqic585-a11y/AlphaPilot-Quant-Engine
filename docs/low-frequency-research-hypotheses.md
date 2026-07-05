# Low-Frequency Research Hypotheses

V13.4.31 defines five first-pass research hypotheses. Each direction should begin with at most 4-6 core conditions.

## LF-HYP-001 BTC/ETH/SOL 4h Trend Following

Thesis:

```text
On mainstream coins, a 4h trend-following structure may be more stable than 1h high-frequency indicator signals.
```

Draft conditions:

- 4h close > EMA200
- 4h EMA20 > EMA50
- 4h trend slope positive
- pullback then reclaim EMA20

Direction: long only.

## LF-HYP-002 BTC/ETH/SOL 4h Bear Rejection Short

Thesis:

```text
On mainstream coins, 4h rebound-failure shorts may be more stable than broad 1h short conditions.
```

Draft conditions:

- 4h close < EMA200
- 4h EMA20 < EMA50
- price rebounds near EMA20 or EMA50
- 4h close weakens after rebound

Direction: short only.

## LF-HYP-003 1d Regime plus 4h Entry

Thesis:

```text
A 1d regime filter paired with 4h entries may reduce noisy trades compared with single-timeframe 1h logic.
```

Draft conditions:

- 1d regime label available
- 4h setup direction agrees with 1d context
- avoidScore remains below threshold
- entry occurs after 4h confirmation candle

Direction: long or short, evaluated separately.

## LF-HYP-004 Breakout Retest on Mainstream Coins

Thesis:

```text
4h breakout or breakdown retest structures may provide cleaner context than pure moving-average pursuit.
```

Draft conditions:

- break above recent N-bar high or below recent N-bar low
- retest holds the breakout or breakdown area
- volume does not contract materially
- avoidScore remains low

Direction: long breakout retest and short breakdown retest as separate modules.

## LF-HYP-005 NoTrade as Active Decision

Thesis:

```text
In bear, crash, or high-volatility regimes, actively choosing no trade may outperform forced low-quality entries.
```

Draft conditions:

- bear, crash, or high-volatility regime present
- direction scores are conflicted
- volatility or drawdown risk elevated
- setup quality below research threshold

Direction: avoidance module.
