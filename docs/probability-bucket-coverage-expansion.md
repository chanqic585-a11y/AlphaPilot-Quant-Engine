# Probability Bucket Coverage Expansion

V13.4.19 compares the original V13.4.14 score table with four coarsened bucket
schemes.

## Scheme A - Remove Time Buckets

V13.4.14 does not store `timeOfDay` or `dayOfWeek`, so Scheme A is a baseline
same-dimension table.

```text
bucketCount: 283
researchGatePassBucketCount: 0
exploratoryGatePassBucketCount: 2
```

## Scheme B - Merge RSI / EMA / Bollinger Buckets

Scheme B merges RSI into `low/middle/high`, EMA distance into
`near_or_below/extended`, and Bollinger position into two broad zones.

```text
bucketCount: 145
researchGatePassBucketCount: 0
exploratoryGatePassBucketCount: 6
```

## Scheme C - Regime + Liquidity + BTC Only

Scheme C keeps only the broad regime, liquidity bucket, and BTC state.

```text
bucketCount: 27
researchGatePassBucketCount: 2
exploratoryGatePassBucketCount: 8
```

## Scheme D - Regime + Module + Volatility

Scheme D derives module type from regime because the original probability table
does not store module type directly.

```text
bucketCount: 22
researchGatePassBucketCount: 2
exploratoryGatePassBucketCount: 5
```

## Limitation

The full raw probability sample dataset is not committed. Coarsening therefore
uses the existing bucket-level table. Profit factor is a sample-count weighted
bucket-level approximation, not a raw win/loss recomputation.

## Research Conclusion

Coarsening creates research candidates in broad schemes C and D. This suggests
the original bucket design is too sparse for the current dataset. It does not
approve trading. Any candidate wiring must be handled in a separate backtest
planning version.
