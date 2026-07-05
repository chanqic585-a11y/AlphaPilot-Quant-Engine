# AlphaPilot V13.4.30 Short Rejection Failure Review

V13.4.30 reviews the V13.4.29 short-only 1h research failure and archives it as a negative research asset. It does not modify strategy code, run a new backtest, enter Dry-run, or approve live trading.

## Status

- currentStatus: failed_research_current_sample
- researchWorthContinuing: False
- dryRunApproved: False
- liveTradingApproved: False
- sourceShortReport: reports\v13_4_29_short_rejection_1h_report.json

## Overall Failure

- tradeCount: 5052
- totalReturnPct: -99.9966
- maxDrawdownPct: 99.9966
- profitFactor: 0.782
- winRatePct: 29.711
- conclusion: The expanded short-only sample is a structural failure, not a tuning candidate.

## Trade Frequency Review

- averageTradesPerPair: 180.4286
- averageTradesPerMonth: 842.0
- topPairTradeShare: 0.0901
- conclusion: The strategy generated too many entries for a fragile short thesis.

## Payoff Review

- roughBreakevenWinRatePctBeforeCosts: 33.3333
- actualWinRatePct: 29.711
- stopLossTrades: 3532
- roiTrades: 1395
- conclusion: The theoretical payoff was undermined by low win rate, frequent stop losses, and costs.

## Short Squeeze / Wrong Timing Review

- regimeBackgroundAvailable: True
- perTradeRegimeAttributionAvailable: False
- dominantRegimes: bear, sideways, bull
- conclusion: Wrong-timing and squeeze risk cannot be ruled out and must be instrumented before revival.

## Pair / Month Review

- pairMonthlyBreakdownAvailable: True
- worstPairsByReturnPct:
  - TOTAL: trades=5052 profitTotalPct=-100.0 profitFactor=0.782030949148284
  - APT/USDT:USDT: trades=153 profitTotalPct=-8.2 profitFactor=0.5346848872200958
  - OP/USDT:USDT: trades=378 profitTotalPct=-8.12 profitFactor=0.5767001760040785
  - PEPE/USDT:USDT: trades=103 profitTotalPct=-7.05 profitFactor=0.5990492348428254
  - ADA/USDT:USDT: trades=139 profitTotalPct=-6.97 profitFactor=0.6495548452345794
- worstMonthsByProfitAbs:
  - 31/01/2026: trades=1430 profitAbs=-593.49271282 profitFactor=0.82462836
  - 28/02/2026: trades=2327 profitAbs=-405.6711446 profitFactor=0.66239165
  - 31/03/2026: trades=832 profitAbs=-0.72650059 profitFactor=0.55757741
  - 30/04/2026: trades=307 profitAbs=-0.05434228 profitFactor=0.63411763
  - 30/06/2026: trades=115 profitAbs=-0.01242719 profitFactor=0.68422266
- conclusion: Losses were broad enough that no single pair rescue is a sufficient fix.

## Exit Reason Review

- exitReasonBreakdownAvailable: True
- stopLossSharePct: 69.9129
- stopLoss: {'exitReason': 'stop_loss', 'trades': 3532, 'profitTotalPct': -456.78, 'wins': 0, 'losses': 3532, 'winRatePct': 0.0}
- roi: {'exitReason': 'roi', 'trades': 1395, 'profitTotalPct': 353.66, 'wins': 1395, 'losses': 0, 'winRatePct': 100.0}
- conclusion: stop_loss was the primary loss source; time stop was too small to offset the core failure.

## Cost / Slippage Review

- slippageReviewAvailable: True
- totalReturnPct: -99.9966
- slippageAdjustedTotalReturnPct: -217.1225
- slippageImpactPct: -117.1259
- profitFactor: 0.782
- slippageAdjustedProfitFactor: 0.5966
- conclusion: Costs worsened an already failing strategy; future short research must reduce frequency.

## Negative Research Rules

- SHORT_NEG_001: Do not mistake a small set of loose conditions for a constrained strategy.
- SHORT_NEG_002: Do not rely only on EMA rejection plus MACD/RSI weakening for short research.
- SHORT_NEG_003: A loose shortScore can create overtrading even when each condition looks reasonable alone.
- SHORT_NEG_004: Short research must explicitly monitor rebound and squeeze risk.
- SHORT_NEG_005: Short research must reduce trade frequency or use stronger trigger quality before expansion.
- SHORT_NEG_006: Regime context cannot be ignored, but it should be evaluated before becoming a hard switch.
- SHORT_NEG_007: Do not try to rescue a deeply negative expanded backtest with small parameter tweaks.
- SHORT_NEG_008: Failed research strategies should be archived as benchmark/reference assets, not deleted.
- SHORT_NEG_009: Any future short strategy must include per-trade regime attribution before next-stage review.
- SHORT_NEG_010: Any future short strategy must report separated direction metrics, costs, and stop-loss sources.

## Future Short Research Recommendations

- Do not continue tuning AlphaPilotShortRejection1HV01 as the active short mainline.
- Wait for public funding and open-interest data before another short-focused research track.
- Require much lower trade frequency before any expanded short backtest.
- Use stronger triggers such as failed breakout, lower-high confirmation, or relative weakness.
- Add per-trade regime attribution before evaluating short strategy continuation.
- Start any future short candidate on BTC/ETH/SOL or Top10 only before supported-pair expansion.

## Safety Boundary

- no strategy modification
- no new backtest
- no Dry-run
- no real API key
- no Trade API / Withdraw API
- no account or position reads
- no real orders
- no auto trading

Warnings:

- Research gate failed; this short-only idea is not approved for continuation without redesign.
