# AlphaPilot V13.4.22 Factor Evaluation Summary

This report evaluates point-in-time manual factors against forward labels. It is research-only and does not create a trading strategy, run a Freqtrade backtest, enter Dry-run, use API keys, read accounts, create orders, or auto trade.

## Evaluation Status

- status: success
- factorCount: 16
- evaluatedFactorCount: 16
- sampleCount: 124111
- validLabelCount: 123439
- horizons: 4, 8, 12, 24
- primaryHorizon: 12
- quantiles: 5
- TP / SL labels: +0.05 / -0.025

## Top Factors By RankIC

- volatility_3d: meanRankIC=-0.05978581
- atr_pct: meanRankIC=-0.05667593
- volatility_24h: meanRankIC=-0.05478825
- distance_to_ema20: meanRankIC=-0.04514636
- momentum_12: meanRankIC=-0.04436032
- relative_strength_vs_btc: meanRankIC=-0.04436032
- momentum_3: meanRankIC=-0.03362539
- reversal_3: meanRankIC=0.03362539

## Top Factors By Q5-Q1 Spread

- trend_strength: topBottomSpread=0.00207277
- distance_to_ema50: topBottomSpread=0.00165647
- volume_expansion_3d: topBottomSpread=0.00163257
- bollinger_position: topBottomSpread=0.00123559
- volume_expansion_24h: topBottomSpread=0.00104826
- distance_to_ema20: topBottomSpread=0.00100324
- momentum_12: topBottomSpread=0.00099353
- relative_strength_vs_btc: topBottomSpread=0.00099353

## Top Factors By Profit Factor

- trend_strength: profitFactor=1.01541027
- distance_to_ema50: profitFactor=0.99401297
- atr_pct: profitFactor=0.99390668
- volume_expansion_3d: profitFactor=0.98981413
- volatility_24h: profitFactor=0.98533611
- volume_expansion_24h: profitFactor=0.98182114
- distance_to_ema20: profitFactor=0.97428999
- bollinger_position: profitFactor=0.9704824

## Candidate Factors

- none

## Low Coverage Factors

- volatility_3d: coveragePct=99.4585
- volume_expansion_3d: coveragePct=99.4811
- momentum_12: coveragePct=99.7293
- relative_strength_vs_btc: coveragePct=99.7293
- bollinger_position: coveragePct=99.797
- volatility_24h: coveragePct=99.8646
- volume_expansion_24h: coveragePct=99.8872
- mean_reversion_distance: coveragePct=99.8872

## Unstable Factors

- momentum_3: months=False, pairs=True, regimes=True
- momentum_12: months=True, pairs=False, regimes=True
- reversal_3: months=False, pairs=False, regimes=False
- volume_expansion_24h: months=True, pairs=False, regimes=True
- distance_to_ema20: months=True, pairs=False, regimes=True
- bollinger_position: months=True, pairs=False, regimes=True
- volatility_3d: months=False, pairs=False, regimes=True
- relative_strength_vs_btc: months=True, pairs=False, regimes=True
- liquidity_rank: months=True, pairs=False, regimes=True
- atr_pct: months=True, pairs=False, regimes=True

## No-Lookahead Boundary

- Features are point-in-time and use only current or historical rows.
- Forward labels use future candles only as evaluation targets.
- Forward labels do not alter factor values, sample selection, or universe membership.
- Candidate factors are research artifacts, not signals or orders.

## Warnings

- Forward labels are evaluation targets only and do not feed back into factor computation.
- Same-bar TP/SL collisions are handled conservatively as SL-first for label accounting.
- Conservative same-bar TP/SL collision count: 56.
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
