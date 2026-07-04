"""Manual factor library V01 design.

The library is a static research specification. It does not compute factors in
V13.4.20 and it is not wired to any strategy.
"""

from __future__ import annotations

from alphapilot.factors.factor_schema import ManualFactorSpec


def _factor(
    factor_id: str,
    description: str,
    formula: str,
    required_fields: list[str],
    expected_direction: str,
    applicable_regime: list[str],
    risk_notes: list[str],
) -> ManualFactorSpec:
    return ManualFactorSpec(
        factorId=factor_id,
        name=factor_id.replace("_", " ").title(),
        description=description,
        formula=formula,
        requiredFields=required_fields,
        expectedDirection=expected_direction,
        applicableRegime=applicable_regime,
        riskNotes=risk_notes,
        outputColumn=factor_id,
    )


MANUAL_FACTOR_LIBRARY_V01 = [
    _factor("momentum_3", "Short horizon momentum over three bars.", "ts_return(close, 3)", ["close"], "higher_may_be_stronger", ["trend", "breakout"], ["Can overfit during choppy regimes."]),
    _factor("momentum_12", "Medium horizon momentum over twelve bars.", "ts_return(close, 12)", ["close"], "higher_may_be_stronger", ["trend"], ["May lag fast reversals."]),
    _factor("reversal_3", "Short horizon reversal pressure.", "-ts_return(close, 3)", ["close"], "higher_may_indicate_rebound", ["mean_reversion"], ["Can fight strong trends."]),
    _factor("volume_expansion_24h", "Volume expansion versus recent average.", "volume / ts_mean(volume, 24)", ["volume"], "higher_indicates_attention", ["breakout", "trend"], ["Volume spikes can be exhaustion rather than continuation."]),
    _factor("volume_expansion_3d", "Three-day style volume expansion on 1h bars.", "ts_mean(volume, 24) / ts_mean(volume, 72)", ["volume"], "higher_indicates_attention", ["breakout", "trend"], ["Requires enough history for stable comparison."]),
    _factor("distance_to_ema20", "Distance from close to EMA20.", "(close - ts_ema(close, 20)) / ts_ema(close, 20)", ["close"], "context_dependent", ["trend", "mean_reversion"], ["Large distance can mean strength or overextension."]),
    _factor("distance_to_ema50", "Distance from close to EMA50.", "(close - ts_ema(close, 50)) / ts_ema(close, 50)", ["close"], "context_dependent", ["trend", "mean_reversion"], ["Slower signal can lag new regimes."]),
    _factor("bollinger_position", "Position inside a Bollinger-style range.", "(close - lower_band) / (upper_band - lower_band)", ["close", "upper_band", "lower_band"], "context_dependent", ["mean_reversion", "breakout"], ["Band position needs volatility context."]),
    _factor("volatility_24h", "Short-term realized volatility.", "ts_std(returns_1, 24)", ["returns_1"], "lower_or_moderate_preferred", ["trend", "mean_reversion", "avoid"], ["Very low volatility can imply no opportunity."]),
    _factor("volatility_3d", "Three-day realized volatility on 1h bars.", "ts_std(returns_1, 72)", ["returns_1"], "context_dependent", ["trend", "breakout", "avoid"], ["High volatility can improve movement but harm execution."]),
    _factor("relative_strength_vs_btc", "Pair return relative to BTC.", "ts_return(close, 12) - btcReturn_12", ["close", "btcReturn"], "higher_may_be_stronger", ["trend"], ["BTC proxy must be time-aligned."]),
    _factor("liquidity_rank", "Cross-sectional liquidity rank.", "rank(quoteVolume)", ["quoteVolume"], "higher_preferred", ["all"], ["Liquidity is a research filter, not alpha by itself."]),
    _factor("atr_pct", "ATR as a percentage of close.", "atr / close", ["atr", "close"], "context_dependent", ["trend", "mean_reversion", "avoid"], ["Requires consistent ATR calculation."]),
    _factor("trend_strength", "EMA trend structure strength.", "(ts_ema(close, 20) - ts_ema(close, 50)) / close", ["close"], "higher_may_be_stronger", ["trend"], ["Can fail during late trend exhaustion."]),
    _factor("mean_reversion_distance", "Distance from mean for rebound research.", "-abs((close - ts_mean(close, 24)) / ts_std(close, 24))", ["close"], "higher_means_less_extreme", ["mean_reversion"], ["Extreme distance needs separate direction logic."]),
    _factor("breakout_pressure", "Pressure near recent highs with volume.", "rank(close / ts_max(high, 24)) + rank(volume / ts_mean(volume, 24))", ["close", "high", "volume"], "higher_may_indicate_breakout_pressure", ["breakout"], ["Breakout pressure needs false-breakout control."]),
]


def build_manual_factor_library_v01() -> list[dict[str, object]]:
    return [factor.to_dict() for factor in MANUAL_FACTOR_LIBRARY_V01]


def manual_factor_output_columns() -> list[str]:
    return [factor.outputColumn or factor.factorId for factor in MANUAL_FACTOR_LIBRARY_V01]
