# Factor Operator Subset

V13.4.20 defines a small explainable operator subset for manual factor research.

This version does not implement automatic factor search or genetic programming.

## Time-Series Operators

```text
ts_mean
ts_std
ts_rank
ts_zscore
ts_delta
ts_return
ts_ema
ts_corr
ts_min
ts_max
```

## Cross-Sectional Operators

```text
rank
zscore
winsorize
scale
demean
```

## Combination Operators

```text
add
sub
mul
div_safe
where
clip
```

## Explicitly Excluded

```text
genetic programming
automatic complex expression generation
deep learning factors
reinforcement learning factors
```

The first factor research iteration should remain auditable and easy to
inspect.
