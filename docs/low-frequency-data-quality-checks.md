# Low-Frequency Data Quality Checks

The V13.4.32 checker reads local public Freqtrade OHLCV files and checks:

- file availability
- required columns
- candle count
- duplicate timestamps
- missing candle rate
- invalid OHLC rows
- zero or negative prices
- negative volume rows
- extreme close-to-close returns
- zero-volume streaks

The checker does not fabricate missing data. Missing or unreadable data is reported as unavailable or insufficient.

Quality statuses:

- `valid`: enough candles and no serious structural issues
- `warning`: usable but with minor gaps or notable warnings
- `invalid`: insufficient candles or structural OHLCV issues
- `unavailable`: missing or unreadable local data

Generated report:

```text
reports/v13_4_32_low_frequency_data_report.json
```
