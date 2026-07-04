# V13.4.12 Dynamic Regime Strategy Summary

## Decision

- strategyName: AlphaPilot Dynamic Regime Strategy V0.1
- currentStatus: specification_only
- dryRunApproved: False
- liveTradingApproved: False
- nextStepRecommendation: V13.4.13 - Historical Dynamic Universe Builder

## Architecture Flow

- public_exchange_data
- dynamic_universe_builder
- historical_universe_snapshots
- market_regime_router
- trend_or_mean_reversion_module
- probability_score
- liquidity_gate
- risk_gate
- backtest_research

## Dynamic Universe

- moduleId: DynamicUniverseV01
- recommended selection size: 10
- maximum selection size: 15
- historical snapshots are required to avoid lookahead bias.

## Regime Router

- regimes: trend, mean_reversion, avoid
- breakout is reserved for a later version.

## Strategy Modules

- trend: TrendContinuationModuleV01
- mean reversion: MeanReversionModuleV01
- breakout: reserved_for_later_version

## Probability Score

- moduleId: ProbabilityScoreV01
- minimum sample count: 50
- minimum hit TP before SL probability: 0.45
- minimum profit factor: 1.2
- insufficient samples return observe_only.

## Liquidity and Risk Gates

- V13.4.11 Liquidity Gate is required before future Dry-run or live review.
- Risk Gate remains the final veto layer.

## Safety

V13.4.12 is a specification-only version. No strategy code, data download, backtest, Dry-run, real API key, Trade API, Withdraw API, account read, position read, order creation, or auto trading was added.
