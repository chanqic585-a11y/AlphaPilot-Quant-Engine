# AlphaPilot V13.4.22 Factor Evaluation Summary

This report evaluates point-in-time manual factors against forward labels. It is research-only and does not create a trading strategy, run a Freqtrade backtest, enter Dry-run, use API keys, read accounts, create orders, or auto trade.

## Evaluation Status

- status: success
- factorCount: 16
- evaluatedFactorCount: 16
- sampleCount: 597046
- validLabelCount: 596374
- horizons: 4, 8, 12, 24
- primaryHorizon: 12
- quantiles: 5
- TP / SL labels: +0.05 / -0.025

## Top Factors By RankIC

- atr_pct: meanRankIC=-0.06840921
- volatility_24h: meanRankIC=-0.06411356
- volatility_3d: meanRankIC=-0.06083201
- distance_to_ema50: meanRankIC=-0.03571791
- distance_to_ema20: meanRankIC=-0.03136924
- trend_strength: meanRankIC=-0.02893168
- momentum_12: meanRankIC=-0.0286097
- relative_strength_vs_btc: meanRankIC=-0.0286097

## Top Factors By Q5-Q1 Spread

- bollinger_position: topBottomSpread=0.00072899
- liquidity_rank: topBottomSpread=0.00053283
- distance_to_ema20: topBottomSpread=0.00049152
- volume_expansion_24h: topBottomSpread=0.00048734
- momentum_12: topBottomSpread=0.00046246
- relative_strength_vs_btc: topBottomSpread=0.00046246
- breakout_pressure: topBottomSpread=0.00044409
- momentum_3: topBottomSpread=0.00042879

## Top Factors By Profit Factor

- liquidity_rank: profitFactor=1.03940325
- volume_expansion_24h: profitFactor=1.02252872
- breakout_pressure: profitFactor=1.01639244
- bollinger_position: profitFactor=1.01583028
- momentum_3: profitFactor=1.00955889
- distance_to_ema20: profitFactor=1.00934847
- momentum_12: profitFactor=1.00693206
- relative_strength_vs_btc: profitFactor=1.00693206

## Candidate Factors

- none

## Low Coverage Factors

- volatility_3d: coveragePct=99.8874
- volume_expansion_3d: coveragePct=99.8921
- momentum_12: coveragePct=99.9437
- relative_strength_vs_btc: coveragePct=99.9437
- bollinger_position: coveragePct=99.9578
- volatility_24h: coveragePct=99.9719
- volume_expansion_24h: coveragePct=99.9766
- mean_reversion_distance: coveragePct=99.9766

## Unstable Factors

- momentum_3: months=False, pairs=False, regimes=True
- momentum_12: months=True, pairs=False, regimes=True
- reversal_3: months=False, pairs=False, regimes=False
- volume_expansion_3d: months=False, pairs=False, regimes=False
- distance_to_ema20: months=True, pairs=False, regimes=True
- distance_to_ema50: months=False, pairs=True, regimes=True
- bollinger_position: months=True, pairs=False, regimes=True
- volatility_24h: months=False, pairs=False, regimes=False
- volatility_3d: months=False, pairs=False, regimes=False
- relative_strength_vs_btc: months=True, pairs=False, regimes=True

## No-Lookahead Boundary

- Features are point-in-time and use only current or historical rows.
- Forward labels use future candles only as evaluation targets.
- Forward labels do not alter factor values, sample selection, or universe membership.
- Candidate factors are research artifacts, not signals or orders.

## Warnings

- Forward labels are evaluation targets only and do not feed back into factor computation.
- Same-bar TP/SL collisions are handled conservatively as SL-first for label accounting.
- Conservative same-bar TP/SL collision count: 779.
- Research-only factor evaluation. No strategy code, backtest, Dry-run, API key, account read, order, or auto trading was used.
- Forward labels are evaluation-only and do not feed back into factor computation or sample selection.

## Safety Boundary

- dryRunApproved: False
- liveTradingApproved: False
- no strategy implementation
- no backtest execution
- no Trade API / Withdraw API
- no real API key
- no account or position reads
- no real orders
- no auto trading

Next step: V13.4.23 should implement a benchmark strategy suite or design factor-based hypotheses only after research review.
