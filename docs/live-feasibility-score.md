# Live Feasibility Score

Live Feasibility Score is a research readiness score. It is not a prediction of
profit and not permission to trade.

## Inputs

```text
backtestQuality
slippageRobustness
liquidityQuality
tradeFrequency
pairConcentration
drawdownRisk
lossStreakRisk
executionDataAvailability
shadowTradingReadiness
riskGateReadiness
hasShadowTradingResults
```

## Levels

```text
0-39   not_live_feasible
40-59  research_only
60-74  shadow_ready
75-84  dry_run_candidate
85+    controlled_live_candidate
```

## Important Cap

If `hasShadowTradingResults` is false, the score is capped below Dry-run
candidate levels. This prevents a positive backtest from skipping execution
reality validation.

## Current V13.4.11 Use

The V13.4.11 generated report applies the score to the failed Trend Pullback
research context. The expected result remains research-only:

```text
dryRunApproved = false
liveTradingApproved = false
```

## Safety Boundary

The score is a research gate. It does not connect to exchanges, does not place
orders, and does not approve real trading.

