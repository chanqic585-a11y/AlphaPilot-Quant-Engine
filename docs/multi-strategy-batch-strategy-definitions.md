# Multi-Strategy Batch Strategy Definitions

V13.4.35 uses one Freqtrade strategy file with eight research-only strategy classes.

```text
user_data/strategies/AlphaPilotLowFrequencyStrategyBatchV01.py
```

## Strategy Classes

| Class | Direction | Core Idea |
| --- | --- | --- |
| AlphaPilotBatchA_EMATrendLong4H | long only | EMA trend continuation long |
| AlphaPilotBatchB_EMATrendShort4H | short only | EMA trend continuation short |
| AlphaPilotBatchC_BreakoutRetestLong4H | long only | Breakout retest long |
| AlphaPilotBatchD_BreakdownRetestShort4H | short only | Breakdown retest short |
| AlphaPilotBatchE_BollingerReversionLong4H | long only | Bollinger lower-band reclaim |
| AlphaPilotBatchF_BollingerReversionShort4H | short only | Bollinger upper-band rejection |
| AlphaPilotBatchG_RelativeStrengthLong4H | long only | Relative strength continuation versus BTC |
| AlphaPilotBatchH_VolatilityCompressionBreakout4H | long only | Volatility compression breakout |

## Shared Indicators

The batch uses:

- EMA20 / EMA50 / EMA200
- RSI14
- MACD / signal / histogram
- ATR14
- volumeRatio
- Bollinger Bands 20 / 2
- recentReturn3Bars
- recentHigh20 / recentLow20
- priorHigh20 / priorLow20
- BTC 12-bar relative return when available

## Shared Boundary

Every class is research-only and does not approve Dry-run, live trading, private exchange API use, account access, order creation, or auto trading.

## Runtime Note

The first V13.4.35 batch run found a shared relative-strength merge bug. The fix only corrected the BTC return column name after pandas merge suffixing. It did not change strategy thresholds or tune parameters after seeing results.
