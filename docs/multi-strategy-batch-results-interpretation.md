# Multi-Strategy Batch Results Interpretation

V13.4.35 is a completed real batch research run with a negative result.

## Leaderboard

| Rank | Strategy | Direction | Trades | Return % | Slippage Return % | Max DD % | Worth Continuing |
| ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | AlphaPilotBatchH_VolatilityCompressionBreakout4H | long only | 121 | -31.9496 | -49.6662 | 37.5015 | false |
| 2 | AlphaPilotBatchF_BollingerReversionShort4H | short only | 338 | -57.0471 | -92.1595 | 62.9266 | false |
| 3 | AlphaPilotBatchG_RelativeStrengthLong4H | long only | 501 | -62.3265 | -111.0704 | 64.5237 | false |
| 4 | AlphaPilotBatchC_BreakoutRetestLong4H | long only | 384 | -67.9863 | -105.6797 | 72.25 | false |
| 5 | AlphaPilotBatchD_BreakdownRetestShort4H | short only | 330 | -71.2062 | -113.5295 | 76.9301 | false |
| 6 | AlphaPilotBatchE_BollingerReversionLong4H | long only | 336 | -77.558 | -104.3433 | 78.1229 | false |
| 7 | AlphaPilotBatchA_EMATrendLong4H | long only | 814 | -88.79 | -134.7314 | 90.276 | false |
| 8 | AlphaPilotBatchB_EMATrendShort4H | short only | 1209 | -97.5012 | -152.9234 | 97.8948 | false |

## Decision

No batch strategy is worth continuing in its current form.

The best candidate, volatility compression breakout, reduced trade count and drawdown compared with V13.4.34, but still lost money and failed the slippage-adjusted profit-factor hurdle.

## Research Implication

The result suggests that simple BTC/ETH/SOL 4h OHLCV-only rules are not enough for the current AlphaPilot route.

Recommended next step:

```text
V13.4.36 - OHLCV Strategy Batch Failure Review and Funding/OI Route Start
```

This should remain research-only. It should not approve Dry-run or live trading.
