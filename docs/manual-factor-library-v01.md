# Manual Factor Library V01

V13.4.21 turns the V13.4.20 manual factor design into computable local research
features.

## Factors

The implemented factor columns are:

```text
momentum_3
momentum_12
reversal_3
volume_expansion_24h
volume_expansion_3d
distance_to_ema20
distance_to_ema50
bollinger_position
volatility_24h
volatility_3d
relative_strength_vs_btc
liquidity_rank
atr_pct
trend_strength
mean_reversion_distance
breakout_pressure
```

Each factor has:

- `factorId`
- `description`
- `formula`
- `requiredFields`
- `applicableRegime`
- `outputColumn`

## Computation Rules

Time-series factors are grouped by pair. Cross-sectional factors are grouped by
timestamp.

Examples:

```text
momentum_12 = close.pct_change(12)
distance_to_ema20 = (close - EMA20) / EMA20
liquidity_rank = cross-sectional rank of quoteVolume at the same timestamp
breakout_pressure = rank(close / rolling_high_24) + rank(volume / mean_volume_24)
```

## Report

The factor computation report is:

```text
reports/v13_4_21_manual_factor_library_report.json
```

It includes:

- computed factor list
- factor definitions
- factor coverage
- average coverage
- no-lookahead rules
- warnings

## Boundary

Manual factors are not trading signals. They are explainable research features
used to evaluate whether future strategy hypotheses have enough evidence.
