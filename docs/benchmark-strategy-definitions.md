# Benchmark Strategy Definitions

This document defines the V13.4.23 benchmark strategies in plain language.

## BenchmarkNoTrade

Zero-action baseline. It records the result of not trading in the selected
historical sample.

## BenchmarkBuyHoldBTC

Report-only passive BTC baseline. It uses local BTC OHLCV data and estimates the
return from the first available close to the last available close in the sample.

## BenchmarkEMATrend

Simple one-hour trend-following reference:

- EMA20 above EMA50
- close above EMA20
- MACD histogram positive
- exit when close weakens below EMA20, or through the configured ROI / stop loss

## BenchmarkRSIMeanReversion

Simple one-hour mean-reversion reference:

- RSI14 below 30
- close near the lower Bollinger Band
- BTC short-term crash context must not block the sample when available
- exit when RSI recovers or close reaches the Bollinger middle band

## BenchmarkMACDVolume

Simple momentum and volume reference:

- MACD line above signal
- MACD histogram improving
- volume ratio at least 1.2
- close above EMA50
- exit when MACD histogram weakens, or through the configured ROI / stop loss

## BenchmarkBollingerRebound

Simple Bollinger rebound reference:

- close reclaims the lower Bollinger Band area
- RSI14 below 45
- volume is not collapsing
- exit near the Bollinger middle band

## BenchmarkTD9Exhaustion

Simple exhaustion-pattern reference:

- local TD buy setup count reaches at least 9
- RSI14 below 45
- BTC short-term crash context must not block the sample when available
- exit when RSI recovers

## Rejected Benchmark Idea

Martingale or inverse averaging is rejected because it increases tail risk and
conflicts with AlphaPilot's risk-first research boundary.

## V13.4.24 Status Update

After V13.4.24 review:

- `BenchmarkNoTrade`: research baseline
- `BenchmarkBuyHoldBTC`: research baseline
- `BenchmarkEMATrend`: failed benchmark
- `BenchmarkRSIMeanReversion`: failed benchmark
- `BenchmarkMACDVolume`: failed benchmark
- `BenchmarkBollingerRebound`: research reference and hypothesis seed only
- `BenchmarkTD9Exhaustion`: failed benchmark
- `RejectedBenchmarkMartingale`: rejected

None of these benchmarks are approved for Dry-run or live trading.
