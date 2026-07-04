# Filter Effectiveness Methodology

This document describes how V13.4.2 measures AlphaPilot Volume Rebound V0.1
filter effectiveness.

## Purpose

The goal is to answer:

```text
Which filters block candidate candles, and how often?
```

It does not answer:

```text
Which parameters should be changed now?
Should the strategy enter Dry-run?
Should the system trade live?
```

## Data Source

The audit reads local public historical OHLCV files produced by Freqtrade:

```text
user_data/data/okx/futures
```

No exchange request is made by the audit report generator. No private endpoint,
API key, account, position, or order capability is used.

## Reconstruction Method

The report generator reconstructs strategy-equivalent indicators offline:

- EMA20
- EMA200
- RSI14
- MACD histogram
- volume ratio
- Bollinger Bands
- 4h trend context
- BTC three-candle return filter

The same V0.1 threshold values are used:

- BTC three-candle crash blocks at `<= -0.01`
- 4h close must be at least `EMA200 * 0.98`
- RSI must be between `30` and `55`
- volume ratio must be at least `1.5`
- MACD histogram must improve from the previous candle
- close must reclaim `EMA20 * 0.995`
- close must be no higher than `Bollinger middle * 1.01`

These are audit calculations only. They do not modify the strategy parameters.

## Primary Skip Reason

The primary skip reason is assigned in deterministic order:

1. `entry_signal_passed`
2. `data_missing`
3. `btc_crash_filter`
4. `weak_4h_trend`
5. `rsi_out_of_range`
6. `volume_ratio_too_low`
7. `macd_not_improving`
8. `ema20_reclaim_failed`
9. `price_too_extended`
10. `unknown`

This makes the distribution readable, but it also means a candle may fail
multiple filters while only the first failed filter is counted as the primary
skip reason.

## Filter Stats

Each filter records:

- pass count
- fail count
- pass rate
- fail rate
- primary blocks

All filters except `data_ready` are measured on data-ready rows. This keeps
missing-data issues separate from strategy-condition failures.

## Signal To Trade Gap

The final entry count can differ from actual trade count because Freqtrade also
applies engine-level constraints such as available wallet, open trade slots,
pair locks, and execution timing.

V13.4.2 therefore reports both:

- final entry count
- actual trade count

## Limitations

The audit is an offline reconstruction from local OHLCV data. It should be used
as evidence for V13.4.3 design discussions, not as approval for Dry-run or live
trading.
