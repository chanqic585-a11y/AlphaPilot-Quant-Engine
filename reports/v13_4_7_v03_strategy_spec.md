# V13.4.7 V03 Strategy Specification

## Selected Direction

- Selected direction: V03A+D
- Strategy ID: alpha_trend_pullback_1h_v01
- Strategy name: AlphaPilot Trend Pullback 1H V0.1
- Status: spec_only
- Dry-run approved: False

This is a specification only. It is not a Freqtrade strategy implementation.

## Selection Reasons

- V0.1/V0.2 15m signals were too dense and cost-sensitive in expanded validation.
- Raising the primary timeframe to 1h directly addresses noise, fee drag, and slippage sensitivity.
- Trend pullback continuation addresses weak-rebound failures by requiring clearer 4h/1h structure.
- The selected direction avoids continuing small threshold edits inside the failed 15m rebound framework.
- V03A provides the structural logic, while V03D provides the lower-noise timeframe choice.

## Market Scope

- Exchange: okx
- Market type: USDT swap
- Universe: fixed Top30 supported pairs
- Direction: long_only
- Primary timeframe: 1h
- Higher timeframe: 4h
- BTC filter timeframes: 1h, 4h

V03 first implementation still uses the fixed Top30 supported pair universe. It does not use a dynamic leaderboard.

## Entry Rules

### 4h Trend Filter

- ID: trend_4h_filter
- Timeframe: 4h
- Purpose: Search pullback continuation only when the larger structure is not weak.
- Candidate rules:
  - close_4h > ema200_4h
  - ema20_4h >= ema50_4h
  - ema20_4h_slope >= 0

### BTC Market Safety Filter

- ID: btc_market_safety_filter
- Timeframe: 1h/4h
- Purpose: Avoid altcoin continuation entries during BTC stress.
- Candidate rules:
  - btc_1h_3_candle_change_pct > -1.5
  - btc_4h_close >= btc_4h_ema200
  - btc_1h_macd_hist is not worsening for multiple consecutive candles

### 1h Pullback Location

- ID: pullback_location_filter
- Timeframe: 1h
- Purpose: Enter research sample only near a reasonable trend pullback area, not after extension.
- Candidate rules:
  - close_1h >= ema50_1h
  - close_1h <= ema20_1h * 1.015
  - close_1h >= ema20_1h * 0.985

### 1h Reclaim / Confirmation

- ID: reclaim_confirmation_filter
- Timeframe: 1h
- Purpose: Require renewed strength instead of entering because price is merely lower.
- Candidate rules:
  - close_1h > ema20_1h
  - macd_hist_1h > macd_hist_1h.shift(1)

### Volume Quality

- ID: volume_quality_filter
- Timeframe: 1h
- Purpose: Require moderate confirmation while avoiding overly strict 15m-style thresholds.
- Candidate rules:
  - volume_ratio_1h >= 1.2
- Future variants:
  - volume_ratio_1h >= 1.3
  - volume_ratio_1h >= 1.5

### No-Chase Filter

- ID: no_chase_filter
- Timeframe: 1h
- Purpose: Avoid entering after the 1h move is already extended.
- Candidate rules:
  - close_1h <= ema20_1h * 1.02
  - rsi14_1h <= 65

### Risk Quality Filter

- ID: risk_quality_filter
- Timeframe: 1h
- Purpose: Track implementation candidates for candle quality and ATR risk.
- Candidate rules:
  - atr_pct_1h is not extreme
  - current candle body is not overextended
  - upper wick is not excessive
- Implementation status: optional_for_v13_4_8

## Exit Profiles

### ExitProfileA

- Status: recommended_first_implementation
- Stoploss: -2.5%
- Take profit: +5%
- Time stop: exit after 8 closed 1h candles if trade is not profitable
- Momentum exit: only evaluate momentum exit when trade is profitable
- Reason: Simple fixed profile with wider reward/risk than V0.1/V0.2 1:1 payoff.

### ExitProfileB

- Status: candidate_later
- Stoploss: entry - 1.5 * ATR
- Take profit: 2R
- Time stop: exit after 8 closed 1h candles if trade is not profitable
- Momentum exit: only evaluate momentum exit when trade is profitable
- Reason: More adaptive risk model, but implementation and interpretation are more complex.

## Position Sizing

- Risk per trade: 1.0%
- Leverage: 5x configurable research cap
- Margin mode: isolated
- Formula:
  - riskAmount = accountEquity * riskPerTradePct
  - effectiveStopDistance = stopLossPct + feeRate * 2 + slippageRate * 2
  - positionNotional = riskAmount / effectiveStopDistance
  - requiredMargin = positionNotional / leverage

## Quality Gate

- slippage-adjusted total return > 0
- slippage-adjusted profit factor > 1.15
- strict target profit factor >= 1.2
- max drawdown materially below V0.1/V0.2 expanded validation
- max consecutive losses acceptable for the proposed risk model
- trade count sufficient but not excessive
- no single pair dominates profit or loss
- passes BTC/ETH/SOL smoke validation
- passes six-month Top30 validation
- preferably passes longer timerange validation

## Rejected Alternatives

### V03B Breakout Retest Confirmation

- Status: second_priority
- Reason: The structure is clear and useful, but it requires more robust support/resistance, breakout, and retest detection before first implementation.
- Future use: Keep as a follow-up candidate if Trend Pullback 1H does not pass quality gates.

### V03C High Score Signal Only

- Status: future_enhancement_layer
- Reason: A score model is attractive for low-frequency quality control, but first implementation should establish a simpler structural baseline before adding weights.
- Future use: Use later as a scoring layer on top of V03A/V03B style structures.

### V03D 1h Main Timeframe

- Status: merged_into_selected_direction
- Reason: V03D is a timeframe/noise reduction decision, not a complete standalone strategy.
- Future use: Merged into V03A as the primary timeframe for Trend Pullback 1H.

## V13.4.8 Plan

- Add user_data/strategies/AlphaPilotTrendPullback1HV01.py.
- Do not modify old VolumeRebound strategies.
- Implement 1h trend pullback entry logic from this spec.
- Implement ExitProfileA first.
- Run BTC/ETH/SOL smoke backtest.
- If smoke runs without runtime errors, run fixed Top30 six-month validation.
- Generate slippage-adjusted AlphaPilot report.
- Keep dryRunApproved=false unless quality gates are met in a later review.

## Safety

V13.4.7 does not implement strategy code, run backtests, enter Dry-run, use API keys, call Trade API or Withdraw API, read accounts, create orders, or auto trade.
