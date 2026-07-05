# Regime-Aware Long / Short Research

V13.4.31 allows both long and short research, but direction modules must be evaluated separately.

## Scores

Future plans can define:

```text
longScore
shortScore
avoidScore
```

## Interpretation

```text
longScore high and avoidScore low -> long candidate
shortScore high and avoidScore low -> short candidate
avoidScore high or direction scores conflicted -> no trade
```

## Regime Role

Market regime adjusts score weights and risk context. It is not the only hard entry switch.

Examples:

- Bull / recovery can boost longScore and reduce shortScore.
- Bear / crash can boost shortScore and reduce longScore.
- Sideways can increase false-breakout caution.
- High volatility can increase avoidScore.

## Required Reporting

Any future low-frequency research report must include:

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

## Boundary

This framework is research-only. It does not create trades, approve Dry-run, or approve live trading.
