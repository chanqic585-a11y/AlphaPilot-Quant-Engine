# AlphaPilot Trend Pullback 1H V0.1 Spec

This is the V13.4.7 specification for the first V03 strategy candidate.

```text
strategyId: alpha_trend_pullback_1h_v01
name: AlphaPilot Trend Pullback 1H V0.1
status: spec_only
selectedDirection: V03A+D
```

It is not executable strategy code. Implementation is deferred to V13.4.8.

## Positioning

Only trade in clearer bullish trend structures. Wait for price to pull back into
a reasonable 1h trend area, then require renewed strength confirmation.

This is not weak-trend bottom fishing, not 15m high-frequency rebound trading,
not random volume chasing, and not an unfiltered full-market scanner.

## Market Scope

```text
Market: OKX USDT swap
Direction: long only
Primary timeframe: 1h
Higher timeframe: 4h
BTC market filter: BTC 1h / 4h
Universe: fixed Top30 supported pairs
```

V03 first implementation still uses fixed Top30 supported pairs. It does not use
a dynamic leaderboard.

## Entry Logic

### 4h Trend Filter

Candidate rules:

- `4h close > 4h EMA200`
- `4h EMA20 >= 4h EMA50`
- `4h EMA20 slope >= 0`

Purpose: only search for pullback continuation when the larger structure is not
weak.

### BTC Market Safety Filter

Candidate rules:

- BTC 1h latest 3 candles cumulative change is greater than `-1.5%`
- BTC 4h close is not below EMA200
- BTC 1h MACD histogram is not worsening for multiple consecutive candles

Purpose: avoid altcoin continuation entries during BTC stress.

### 1h Pullback Location

First implementation candidate:

- `close >= EMA50`
- `close <= EMA20 * 1.015`
- `close >= EMA20 * 0.985`

Purpose: avoid chasing; wait for a reasonable trend pullback area.

### Reclaim / Confirmation

First implementation candidate:

- `close > EMA20`
- `macd_hist > macd_hist.shift(1)`

Purpose: require renewed strength instead of entering because price is merely
lower.

### Volume Quality

First implementation candidate:

- `volumeRatio >= 1.2`

Future variants for V13.4.8 comparison:

- `volumeRatio >= 1.3`
- `volumeRatio >= 1.5`

### No-Chase Filter

Candidate rules:

- `close <= EMA20 * 1.02`
- `RSI14 <= 65`

### Risk Quality Filter

Optional for V13.4.8:

- ATR% is not extreme
- current candle body is not overextended
- upper wick is not excessive

## Exit Logic

V03 must not default to the old 1:1 payoff.

### ExitProfileA

Recommended first implementation:

- stoploss: `-2.5%`
- take profit: `+5%`
- time stop: exit after 8 closed 1h candles if trade is not profitable
- momentum exit: only when trade is already profitable

### ExitProfileB

Candidate later:

- stoploss: `entry - 1.5 * ATR`
- take profit: `2R`
- time stop: exit after 8 closed 1h candles if trade is not profitable

## Position Sizing

Continue risk-derived position sizing:

```text
riskAmount = accountEquity * riskPerTradePct
effectiveStopDistance = stopLossPct + feeRate * 2 + slippageRate * 2
positionNotional = riskAmount / effectiveStopDistance
requiredMargin = positionNotional / leverage
```

Defaults:

- risk per trade: 1%
- leverage: 5x configurable research cap
- margin mode: isolated

## Quality Gate

Before any Dry-run discussion:

- slippage-adjusted total return > 0
- slippage-adjusted profit factor > 1.15
- strict target profit factor >= 1.2
- max drawdown materially below V0.1/V0.2 expanded validation
- max consecutive losses acceptable
- sufficient but not excessive trade count
- no single pair dominates profit or loss
- BTC/ETH/SOL smoke validation passes
- six-month Top30 validation passes
- preferably longer timerange validation passes

If these gates are not met, the strategy must not enter Dry-run.

## Safety

This spec does not use API keys, does not call Trade API or Withdraw API, does
not read accounts or positions, does not create orders, and does not auto trade.

