# Backtest Report Export

AlphaPilot reports distinguish mock schema samples from real converted
Freqtrade results.

## Mock Report

When no Freqtrade result JSON exists under `user_data/backtest_results`, the
exporter writes:

```text
reports/sample_backtest_report.json
```

The report must contain:

```json
{
  "isMock": true
}
```

This file is useful for schema validation only. It is not a real backtest.

## Real Report

When a Freqtrade JSON result exists, the exporter writes:

```text
reports/latest_backtest_report.json
reports/smoke_backtest_report.json
```

The report must contain:

```json
{
  "isMock": false
}
```

The exporter records the source result path and includes report warnings for
fields that Freqtrade did not provide or for cost models not applied by the
engine.

## Missing Metrics

If Freqtrade does not provide a metric, V13.4 uses `null` rather than inventing
values. The missing field is explained in `reportWarnings` when possible.

## Safety Boundary

Report export reads local files only. It does not use API keys, does not call
exchange private APIs, and does not place orders.
