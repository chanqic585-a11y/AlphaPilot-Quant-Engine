# V13.7.38 Top50 Short-Cycle Backtest Report

- Timerange: `20260101-`
- Requested universe: Top50 OKX USDT swap research pairs
- Backtested universe: 45 pairs with complete 15m/30m/1h/4h local OHLCV
- Excluded missing-data pairs: `TON/USDT:USDT`, `FET/USDT:USDT`, `MANTA/USDT:USDT`, `MKR/USDT:USDT`, `RUNE/USDT:USDT`
- Fee: `0.0005`; slippage stress was not applied in this Freqtrade run.
- Safety: research backtest only; no API key, no Trade API, no Withdraw API, no real account, no orders.

| Candidate | Strategy | TF | Trades | Win Rate | Profit Factor | Expectancy | Total Return | Max DD | Gate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 15m Volume Rebound Candidate | `AlphaPilotVolumeReboundV01` | 15m | 3748 | 38.58% | 0.6892 | -0.2664 | -99.86% | 99.89% | fail_research_gate |
| 1h Trend Pullback Candidate | `AlphaPilotTrendPullback1HV01` | 1h | 681 | 29.52% | 0.6021 | -1.1925 | -81.21% | 83.44% | fail_research_gate |
| 1h Short Rejection Candidate | `AlphaPilotShortRejection1HV01` | 1h | 6286 | 29.81% | 0.5218 | -0.1591 | -100.00% | 100.00% | fail_research_gate |
| 30m Bollinger Mean Reversion Candidate | `AlphaPilotBatchF_BollingerReversionShort4H` | 30m | 3652 | 35.16% | 0.7056 | -0.2738 | -99.98% | 99.98% | fail_research_gate |
| 30m Volatility Compression Breakout Candidate | `AlphaPilotBatchH_VolatilityCompressionBreakout4H` | 30m | 897 | 26.09% | 0.7765 | -0.9903 | -88.83% | 91.97% | fail_research_gate |

## Gate Notes
- 15m Volume Rebound Candidate: winrate_weak, profit_factor_weak, expectancy_non_positive, total_return_non_positive, drawdown_too_high
- 1h Trend Pullback Candidate: winrate_weak, profit_factor_weak, expectancy_non_positive, total_return_non_positive, drawdown_too_high
- 1h Short Rejection Candidate: winrate_weak, profit_factor_weak, expectancy_non_positive, total_return_non_positive, drawdown_too_high
- 30m Bollinger Mean Reversion Candidate: winrate_weak, profit_factor_weak, expectancy_non_positive, total_return_non_positive, drawdown_too_high
- 30m Volatility Compression Breakout Candidate: winrate_weak, profit_factor_weak, expectancy_non_positive, total_return_non_positive, drawdown_too_high