# OHLCV Data Integrity Checks

V13.4.27 checks local public OHLCV files before they are used for expanded
strategy or factor research.

The checker reads only local files under:

```text
user_data/data/okx/futures
```

It does not download data and does not call exchange APIs.

## Checks

For each pair and timeframe, the checker validates:

- pair format such as `BTC/USDT:USDT`
- futures/swap file naming
- required columns: `date`, `open`, `high`, `low`, `close`, `volume`
- UTC timestamp parsing
- monotonic timestamps
- duplicate timestamps
- internal candle gaps
- missing candle rate
- invalid OHLC rows
- negative volume
- zero-volume stretches
- volume spikes
- extreme close-to-close returns

Warning thresholds:

```text
missingRatePct > 5%  -> warning
missingRatePct > 20% -> invalid
abs(1h return) > 30% -> extreme return warning
abs(4h return) > 50% -> extreme return warning
```

## Quote Volume

Raw Freqtrade OHLCV files generally do not include `quoteVolume`. V13.4.27
does not fabricate it in the integrity report. Downstream research layers may
estimate quote volume explicitly and must mark it as estimated.

## Output

Pair-level diagnostics are written to:

```text
reports/v13_4_27_data_quality_by_pair.json
```

Missing files remain missing. They are not replaced with synthetic candles.
