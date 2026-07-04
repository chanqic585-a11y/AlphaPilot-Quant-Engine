# FactorDataPanel Local Data Generation

The V13.4.21 FactorDataPanel is generated from local public OHLCV files.

## Data Loader

`alphapilot/factors/ohlcv_loader.py` is responsible for:

- discovering local Freqtrade OHLCV files
- supporting `.feather`, `.parquet`, `.json`, and `.json.gz`
- normalizing columns to `date/open/high/low/close/volume`
- filtering by timerange
- reporting failed pairs and missing timeframes

If a dependency such as `pyarrow` is missing for feather files, the loader
records a clear error. It does not fabricate OHLCV.

## Panel Builder

`alphapilot/factors/factor_data_panel.py` computes:

- `returns_1`
- `returns_3`
- `returns_6`
- `returns_12`
- `marketReturn`
- `btcReturn`
- `btcReturn_12`
- `liquidityBucket`
- `volatilityBucket`
- `regimeLabel`
- optional historical dynamic universe membership

## Estimated Fields

Freqtrade local OHLCV files do not provide every market microstructure field.
V13.4.21 therefore marks estimated fields explicitly:

```text
quoteVolume = close * volume
quoteVolumeEstimated = true
vwap = (high + low + close) / 3
vwapEstimated = true
```

These are approximations for research features only.

## Dynamic Universe

When `--use-dynamic-universe` is enabled and V13.4.13 snapshots are available,
membership is mapped by snapshot date.

When dynamic universe is not enabled, rows use the loaded local pair universe
fallback and the report records:

```text
universeMembershipSource = local_loaded_pairs_fallback
```

## Safety

The local data generation flow does not call exchange APIs, download data, run
backtests, read accounts, create orders, or auto trade.
