# Shared Official Market Data Design

## Goal

Let every current and future strategy reuse one verified OKX public OHLCV
warehouse by exchange, market type, instrument, timeframe, and coverage instead
of downloading the same history once per strategy data contract.

## Required behavior

1. Every workflow still runs the local non-official research smoke first.
2. Formal evidence only reads OKX public canonical data with a verified manifest
   and matching file hash.
3. Same-contract checkpoints remain the fastest exact reuse path.
4. If another contract already produced a matching canonical partition, the
   collector uses its latest timestamp as the incremental cutoff.
5. Only candles newer than that cutoff are requested. The verified base and new
   tail are merged, validated, and written as a new canonical snapshot.
6. If no new confirmed candle exists, the original canonical file and hash are
   reused directly.
7. A malformed, missing, hash-mismatched, wrong-source, wrong-symbol, or
   wrong-timeframe manifest is ignored and the normal official collection path
   remains available.
8. The rule applies uniformly to 5m, 15m, 1h, 4h, and 1d.
9. One serial official-data worker remains the physical downloader. Multiple
   strategies may wait on the same warehouse, but they do not create competing
   OKX request storms.

## Current selected workflows

- `5m 极端超卖收回 ATR1.2`: 5m, Top50.
- `15m EMA20 回收反弹 ATR1.4`: 15m, Top50.
- `Alpha191 加密因子观察策略`: 5m execution, 15m fallback, and 4h signal,
  Top50.

The first two datasets become reusable inputs for Alpha191. Alpha191 then only
needs missing tails and 4h partitions.

## Data integrity

Shared reuse never changes strategy definitions, target R, costs, walk-forward
requirements, holdouts, or promotion gates. A shared partition remains formal
evidence only after the existing frame validation and snapshot verification
pass. Runtime credentials, private APIs, orders, and Withdraw are outside this
change.

## Failure handling

Manifest discovery is fail-open toward fresh public collection, not toward
formal promotion: an invalid shared candidate is skipped, and the collector
downloads and validates public data normally. Partial page checkpoints never
become reusable completed partitions.
