# AlphaPilot V13.12.0 Factor Research Kernel

This baseline registers legacy factor definitions without recalculating or mutating values.
DSL compatibility is not evidence of profitability or promotion readiness.

## Summary

- Factors: 16
- DSL supported: 11
- DSL blocked: 5
- Legacy candidate factors: 0
- Formal research ready: 0
- Values mutated: false

## Factor Compatibility

| Factor | DSL | Kernel status | Canonical expression |
| --- | --- | --- | --- |
| momentum_3 | true | blocked_missing_formal_statistical_evidence | `safe_divide(delta(close,3),lag(close,3))` |
| momentum_12 | true | blocked_missing_formal_statistical_evidence | `safe_divide(delta(close,12),lag(close,12))` |
| reversal_3 | true | blocked_missing_formal_statistical_evidence | `safe_multiply(-1,safe_divide(delta(close,3),lag(close,3)))` |
| volume_expansion_24h | true | blocked_missing_formal_statistical_evidence | `safe_divide(volume,rolling_mean(volume,24))` |
| volume_expansion_3d | true | blocked_missing_formal_statistical_evidence | `safe_divide(rolling_mean(volume,24),rolling_mean(volume,72))` |
| distance_to_ema20 | false | blocked_unsupported_or_invalid_dsl | `--` |
| distance_to_ema50 | false | blocked_unsupported_or_invalid_dsl | `--` |
| bollinger_position | true | blocked_missing_formal_statistical_evidence | `safe_divide(safe_subtract(close,lower_band),safe_subtract(upper_band,lower_band))` |
| volatility_24h | true | blocked_missing_formal_statistical_evidence | `rolling_std(returns_1,24)` |
| volatility_3d | true | blocked_missing_formal_statistical_evidence | `rolling_std(returns_1,72)` |
| relative_strength_vs_btc | false | blocked_unsupported_or_invalid_dsl | `--` |
| liquidity_rank | true | blocked_missing_formal_statistical_evidence | `cross_sectional_rank(quote_volume)` |
| atr_pct | true | blocked_missing_formal_statistical_evidence | `safe_divide(atr,close)` |
| trend_strength | false | blocked_unsupported_or_invalid_dsl | `--` |
| mean_reversion_distance | false | blocked_unsupported_or_invalid_dsl | `--` |
| breakout_pressure | true | blocked_missing_formal_statistical_evidence | `safe_add(cross_sectional_rank(safe_divide(close,rolling_max(high,24))),cross_sectional_rank(safe_divide(volume,rolling_mean(volume,24))))` |

## Promotion Boundary

All factors remain blocked from formal promotion until point-in-time validation,
purged walk-forward, FDR, Deflated Sharpe, PBO, bootstrap, stability, and cost
stress evidence exists in the new registry.
