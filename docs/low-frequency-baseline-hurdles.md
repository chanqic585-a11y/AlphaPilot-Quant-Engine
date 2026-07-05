# Low-Frequency Baseline Hurdles

Future low-frequency candidates must report against the V13.4.32 baselines before any approval discussion.

Universal hurdles:

- `dryRunApproved=false`
- `liveTradingApproved=false`
- `mustBeatNoTrade=true`
- `mustReportVsBuyHold=true`
- `mustReportVsEqualWeight=true`
- `mustReportRegimeBreakdown=true`
- `mustReportLongShortBreakdown=true`
- `mustReportSlippageAdjustedMetrics=true`

NoTrade hurdle:

- slippage-adjusted return must be above 0
- trade count must not be zero or excessive
- max drawdown must be explicitly judged against risk concept

Pair BuyHold hurdle:

- BTC candidates compare against BuyHold BTC
- ETH candidates compare against BuyHold ETH
- SOL candidates compare against BuyHold SOL
- each report must include excess return, drawdown reduction, and risk-adjusted comparison

EqualWeight hurdle:

- portfolio-style or multi-pair candidates compare against EqualWeight BTC/ETH/SOL
- reports must include excess return, drawdown reduction, and monthly stability comparison

Regime hurdle:

- bull performance
- bear performance
- sideways performance
- crash/high-volatility performance
- no-trade ratio by regime

These hurdles are research gates only. They do not approve Dry-run or live trading.
