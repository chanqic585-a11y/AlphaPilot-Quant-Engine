# AlphaPilot V13.4.31 Low-Frequency Mainstream Coin Research Plan

V13.4.31 narrows the next research track to BTC/ETH/SOL on 4h/1d timeframes. It is a research plan only: no strategy code, no new data download, no backtest, no Dry-run, and no live trading approval.

## Status

- currentStatus: research_plan_only
- dryRunApproved: False
- liveTradingApproved: False
- nextStepRecommendation: V13.4.32 - Low-Frequency Data Preparation and Baseline Builder

## Scope

- pairs: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
- primaryTimeframes: 4h, 1d
- optionalTimeframes: 1h
- excludedFromMainline:
  - Top30 full-market expansion
  - new listings
  - low-liquidity altcoins
  - high-frequency 15m and broad 1h signal loops

## Hypotheses

### LF-HYP-001 - BTC/ETH/SOL 4h Trend Following

- thesis: On mainstream coins, a 4h trend-following structure may be more stable than 1h high-frequency indicator signals.
- direction: long_only
- primaryTimeframe: 4h
- regimeUse: Long candidates receive higher weight in bull, recovery, and neutral-positive regimes; bear/crash regimes reduce long weight.
- coreConditions:
  - 4h close > EMA200
  - 4h EMA20 > EMA50
  - 4h trend slope positive
  - pullback then reclaim EMA20
- validationFocus:
  - trade count reduction versus 1h research
  - slippage-adjusted performance versus NoTrade and BuyHoldBTC
  - drawdown behavior by regime

### LF-HYP-002 - BTC/ETH/SOL 4h Bear Rejection Short

- thesis: On mainstream coins, 4h rebound-failure shorts may be more stable than broad 1h short conditions.
- direction: short_only
- primaryTimeframe: 4h
- regimeUse: Short candidates can appear outside bear regimes, but bull/recovery regimes reduce short weight and require stronger confirmation.
- coreConditions:
  - 4h close < EMA200
  - 4h EMA20 < EMA50
  - price rebounds near EMA20 or EMA50
  - 4h close weakens after rebound
- validationFocus:
  - trade count reduction versus V13.4.29
  - avoidance of chase shorts
  - short results by bull, recovery, bear, and crash regimes

### LF-HYP-003 - 1d Regime plus 4h Entry

- thesis: A 1d regime filter paired with 4h entries may reduce noisy trades compared with single-timeframe 1h logic.
- direction: long_or_short_separated
- primaryTimeframe: 4h
- regimeUse: Regime is not a sole on/off switch; it weights longScore, shortScore, and avoidScore.
- coreConditions:
  - 1d regime label available
  - 4h setup direction agrees with 1d context
  - avoidScore remains below threshold
  - entry occurs after 4h confirmation candle
- validationFocus:
  - whether no-trade decisions reduce drawdown
  - long/short results separated by regime
  - exposure reduction during bear, crash, and high-volatility regimes

### LF-HYP-004 - Breakout Retest on Mainstream Coins

- thesis: 4h breakout or breakdown retest structures may provide cleaner context than pure moving-average pursuit.
- direction: long_and_short_modules
- primaryTimeframe: 4h
- regimeUse: Bull/recovery boosts long retests; bear/crash boosts short breakdown retests; sideways increases false-breakout caution.
- coreConditions:
  - break above recent N-bar high or below recent N-bar low
  - retest holds the breakout or breakdown area
  - volume does not contract materially
  - avoidScore remains low
- validationFocus:
  - false breakout rate
  - reward/risk profile
  - benchmark comparison against simple 4h breakout retest

### LF-HYP-005 - NoTrade as Active Decision

- thesis: In bear, crash, or high-volatility regimes, actively choosing no trade may outperform forced low-quality entries.
- direction: avoidance_module
- primaryTimeframe: 1d
- regimeUse: Regime increases avoidScore and lowers exposure rather than automatically forcing a direction.
- coreConditions:
  - bear, crash, or high-volatility regime present
  - direction scores are conflicted
  - volatility or drawdown risk elevated
  - setup quality below research threshold
- validationFocus:
  - noTradeRatio by regime
  - drawdown avoided versus always-active baselines
  - opportunity cost versus BuyHoldBTC

## Long / Short Framework

- scoreNames: longScore, shortScore, avoidScore
- regimeRole: Market regime adjusts direction scores and risk weight. It is not the only hard entry switch.
- longCandidate: longScore high and avoidScore low
- shortCandidate: shortScore high and avoidScore low
- noTrade: avoidScore high or direction scores conflicted

## Minimal Conditions Philosophy

- maxCoreConditionsPerDirection: 4-6
- avoid:
  - 10+ gate stacks in first version
  - small parameter rescue after structural failure
  - forced trades in noisy regimes

## Benchmark Requirements

- NoTrade
- BuyHoldBTC
- BuyHoldETH
- BuyHoldSOL
- Simple 4h EMA Trend
- Simple 4h Bollinger Rebound
- Simple 4h Breakout Retest

## Evaluation Metrics

- tradeCount
- tradesPerMonth
- totalReturnPct
- slippageAdjustedReturnPct
- profitFactor
- slippageAdjustedProfitFactor
- maxDrawdownPct
- winRate
- maxConsecutiveLosses
- averageHoldingHours
- exposureTimePct
- regimeBreakdown
- longShortBreakdown
- noTradeRatio
- benchmarkComparison

## Data Requirements

- BTC/ETH/SOL 4h OHLCV
- BTC/ETH/SOL 1d OHLCV
- BTC/ETH/SOL 1h OHLCV optional for entry refinement
- market regime labels
- NoTrade baseline
- BuyHoldBTC baseline
- BuyHoldETH baseline
- BuyHoldSOL baseline

Optional future data:

- fundingRate
- openInterest
- spread proxy
- orderbook depth

## Safety Boundary

- no strategy code
- no data download
- no backtest
- no Dry-run
- no real API key
- no Trade API / Withdraw API
- no account or position reads
- no real orders
- no auto trading
