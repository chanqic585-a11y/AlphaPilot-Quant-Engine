# AlphaPilot V13.4.32 Low-Frequency Data and Baseline Report

V13.4.32 prepares BTC/ETH/SOL 4h/1d public OHLCV data and builds report-only NoTrade / BuyHold / EqualWeight baselines.

## Status

- status: completed
- timerange: 20240101-
- pairs: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
- timeframes: 4h, 1d
- data report: reports/v13_4_32_low_frequency_data_report.json

## Data Quality Summary

- pairCount: 3
- timeframeCount: 2
- pairTimeframeCount: 6
- validCount: 6
- warningCount: 0
- invalidCount: 0
- unavailableCount: 0
- minimumCandles: 200

## Baseline Comparison

| Baseline | Pair | Timeframe | Status | Return % | Max DD % | Vol % | Exposure % |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| NoTrade | -- | -- | research_only | 0.0 | 0.0 | 0.0 | 0.0 |
| BuyHold BTC/USDT:USDT | BTC/USDT:USDT | 4h | research_only | 49.3867 | 53.4399 | 47.5225 | 100.0 |
| BuyHold ETH/USDT:USDT | ETH/USDT:USDT | 4h | research_only | -21.2171 | 68.0429 | 66.5194 | 100.0 |
| BuyHold SOL/USDT:USDT | SOL/USDT:USDT | 4h | research_only | -20.6535 | 78.4918 | 82.4955 | 100.0 |
| BuyHold BTC/USDT:USDT | BTC/USDT:USDT | 1d | research_only | 41.4584 | 52.9748 | 48.0248 | 100.0 |
| BuyHold ETH/USDT:USDT | ETH/USDT:USDT | 1d | research_only | -25.3254 | 67.5684 | 69.2645 | 100.0 |
| BuyHold SOL/USDT:USDT | SOL/USDT:USDT | 1d | research_only | -25.1614 | 76.2768 | 81.1811 | 100.0 |
| EqualWeight BTC/ETH/SOL 4h | -- | 4h | research_only | 2.5054 | 62.9563 | 58.6735 | 100.0 |
| EqualWeight BTC/ETH/SOL 1d | -- | 1d | research_only | -3.0095 | 62.315 | 58.9978 | 100.0 |

## Interpretation

- NoTrade is the capital-preservation baseline and opportunity-cost anchor.
- BuyHold baselines describe passive exposure to BTC/ETH/SOL over the selected historical sample.
- EqualWeight baselines describe simple passive mainstream-coin basket exposure.
- Future low-frequency strategies must outperform relevant passive baselines after drawdown, exposure, and stability are considered.
- These baselines are historical research context only. They are not trading advice and not an execution command.

## Future Strategy Benchmark Requirements

- Beat NoTrade on risk-adjusted opportunity cost, not only raw return.
- Compare against same-pair BuyHold for each tested direction and timeframe.
- Compare against EqualWeight BTC/ETH/SOL to avoid mistaking market beta for alpha.
- Report max drawdown, volatility, exposure time, and regime breakdown before any strategy approval.
- Do not approve Dry-run or live trading from V13.4.32 baseline reports.

## Safety Boundary

- strategyImplemented: False
- backtestExecuted: False
- freqtradeBacktestExecuted: False
- dryRunApproved: False
- liveTradingApproved: False
- tradeApiUsed: False
- withdrawApiUsed: False
- apiKeyStored: False
- accountRead: False
- positionRead: False
- orderCreated: False
- autoTradingUsed: False
