# Bucket Key Consistency Check

V13.4.18 compares generated probability bucket keys from the V13.4.17 expanded
report with bucket IDs from the V13.4.14 probability score table.

## Bucket Structure

Expected bucket key structure:

```text
regimeCandidate_liquidityBucket_volatilityBucket_rsiBucket_emaDistanceBucket_bbPositionBucket_btcState
```

Examples:

```text
avoid_low_low_30-45_below_ema20_lower_weak
mean_reversion_low_low_below30_below_ema20_lower_safe
```

## Diagnosis

The score table bucket IDs can be rebuilt from their component fields. Missing
lookups in the expanded report are parseable with the same component domains,
which points to coverage gaps rather than a separator, casing, or ordering bug.

## Safety Boundary

This check does not alter strategy logic, probability thresholds, bucket
definitions, Dry-run settings, API keys, account access, order creation, or any
automatic trading path.
