# AlphaPilot V13.4.21 FactorDataPanel Summary

Status: research-only local data generation.

V13.4.21 reads local public OHLCV files and computes point-in-time manual factors. It does not run a strategy backtest, enter Dry-run, call exchange private APIs, read accounts, create orders, or auto trade.

## Build Status

- status: success
- timerange: 20240101-
- timeframe: 1h
- rowsGenerated: 597046
- sampleRowsWritten: 500
- loadedPairs: 28
- failedPairs: 0
- dynamicUniverseSnapshotsUsed: 0
- universeMembershipSource: local_loaded_pairs_fallback

## Estimated Fields

- quoteVolumeEstimatedCount: 597046
- vwapEstimatedCount: 597046
- quoteVolume uses close * volume because Freqtrade OHLCV does not carry exchange quote volume in this local file set.
- vwap uses typical price fallback `(high + low + close) / 3` and is explicitly marked estimated.

## Manual Factor Library

- factorCount: 16
- computedFactors: momentum_3, momentum_12, reversal_3, volume_expansion_24h, volume_expansion_3d, distance_to_ema20, distance_to_ema50, bollinger_position, volatility_24h, volatility_3d, relative_strength_vs_btc, liquidity_rank, atr_pct, trend_strength, mean_reversion_distance, breakout_pressure
- averageCoveragePct: 99.9675

## Lowest Coverage Factors

- volatility_3d: coverage=99.8874%, missing=672
- volume_expansion_3d: coverage=99.8921%, missing=644
- momentum_12: coverage=99.9437%, missing=336
- relative_strength_vs_btc: coverage=99.9437%, missing=336
- bollinger_position: coverage=99.9578%, missing=252
- volatility_24h: coverage=99.9719%, missing=168
- volume_expansion_24h: coverage=99.9766%, missing=140
- mean_reversion_distance: coverage=99.9766%, missing=140

## No-Lookahead Assurance

- Panel returns use close values from current and prior bars only.
- Manual rolling factors use current and historical rows within each pair only.
- Cross-sectional ranks use pairs at the same timestamp only.
- Dynamic universe membership is read from historical snapshots by snapshot date when enabled.
- No forward labels, trade outcomes, backtest results, or future candles feed into factor values.

## Output Files

- panel sample: reports\v13_7_13_factor_panel_sample.json
- panel report: reports\v13_7_13_factor_panel_report.json
- manual factor report: reports\v13_7_13_manual_factor_library_report.json

## Warnings

- Dynamic universe membership not requested; rows use local loaded pair fallback membership.
- Research-only factor computation. No backtest was run.
- No factor output is a trade signal, order, or live execution instruction.

## Safety Boundary

- dryRunApproved: False
- liveTradingApproved: False
- no API key
- no Trade API
- no Withdraw API
- no account or position reads
- no real orders
- no auto trading

Next step: V13.4.22 - evaluate factor coverage and decide whether to build forward-label factor research.
