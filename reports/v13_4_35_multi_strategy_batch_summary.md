# AlphaPilot V13.4.35 Multi-Strategy Batch Research Backtest

This report ranks research-only Freqtrade backtests. It is not Dry-run, not live trading, and not a trading command.

## Batch Summary

- isMock: False
- timerange: 20240101-
- timeframe: 4h
- pairs: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
- expandedTop10Executed: False
- expandedTop10Reason: Skipped in V13.4.35 because the required BTC/ETH/SOL batch already produced a clear all-strategy failure result.
- strategyCount: 8
- failedStrategies: 0
- bestRawStrategy: AlphaPilotBatchH_VolatilityCompressionBreakout4H
- bestSlippageAdjustedStrategy: AlphaPilotBatchH_VolatilityCompressionBreakout4H

## Leaderboard Raw

| Rank | Strategy | Direction | Trades | Return % | Max DD % | PF | Worth Continuing |
| ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | AlphaPilotBatchH_VolatilityCompressionBreakout4H | long_only | 121 | -31.9496 | 37.5015 | 0.7331063038643343 | False |
| 2 | AlphaPilotBatchF_BollingerReversionShort4H | short_only | 338 | -57.0471 | 62.9266 | 0.658853238977859 | False |
| 3 | AlphaPilotBatchG_RelativeStrengthLong4H | long_only | 501 | -62.3265 | 64.5237 | 0.7932609728929373 | False |
| 4 | AlphaPilotBatchC_BreakoutRetestLong4H | long_only | 384 | -67.9863 | 72.25 | 0.7160982660287256 | False |
| 5 | AlphaPilotBatchD_BreakdownRetestShort4H | short_only | 330 | -71.2062 | 76.9301 | 0.7354624566718212 | False |
| 6 | AlphaPilotBatchE_BollingerReversionLong4H | long_only | 336 | -77.558 | 78.1229 | 0.4529887287465798 | False |
| 7 | AlphaPilotBatchA_EMATrendLong4H | long_only | 814 | -88.79 | 90.276 | 0.6991972431552599 | False |
| 8 | AlphaPilotBatchB_EMATrendShort4H | short_only | 1209 | -97.5012 | 97.8948 | 0.7238215106938185 | False |

## Leaderboard Slippage Adjusted

| Rank | Strategy | Direction | Trades | Slippage Return % | Slippage PF | Worth Continuing |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 1 | AlphaPilotBatchH_VolatilityCompressionBreakout4H | long_only | 121 | -49.6662 | 0.6267 | False |
| 2 | AlphaPilotBatchF_BollingerReversionShort4H | short_only | 338 | -92.1595 | 0.5181 | False |
| 3 | AlphaPilotBatchE_BollingerReversionLong4H | long_only | 336 | -104.3433 | 0.3563 | False |
| 4 | AlphaPilotBatchC_BreakoutRetestLong4H | long_only | 384 | -105.6797 | 0.6034 | False |
| 5 | AlphaPilotBatchG_RelativeStrengthLong4H | long_only | 501 | -111.0704 | 0.6687 | False |
| 6 | AlphaPilotBatchD_BreakdownRetestShort4H | short_only | 330 | -113.5295 | 0.6204 | False |
| 7 | AlphaPilotBatchA_EMATrendLong4H | long_only | 814 | -134.7314 | 0.5895 | False |
| 8 | AlphaPilotBatchB_EMATrendShort4H | short_only | 1209 | -152.9234 | 0.6104 | False |

## Baseline Comparison Summary

- strategyCount: 8
- realBacktestCount: 8
- beatsNoTradeCount: 0
- beatsEqualWeightCount: 0
- researchWorthContinuingCount: 0

## Failed Strategies

- none

## Recommendations

- No strategy passed the first research continuation gate.
- Archive weak OHLCV-only batch candidates as research references.
- Consider V13.4.36 as OHLCV batch failure review and funding/OI route start.

## Safety Boundary

- dryRunApproved: False
- liveTradingApproved: False
- tradeApiUsed: False
- withdrawApiUsed: False
- apiKeyStored: False
- accountRead: False
- positionRead: False
- orderCreated: False
- autoTradingUsed: False
