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

Freqtrade 2026.6 stores backtest output as a zip file and writes
`.last_result.json` as a pointer. The V13.4 exporter follows that pointer,
reads the zip, and converts the internal result JSON.

`latest_backtest_report.json` and `smoke_backtest_report.json` are dynamic rerun
outputs. Fixed release evidence should be copied to a versioned file, for
example:

```text
reports/v13_4_smoke_backtest_report.json
```

The V13.4 versioned report contains a real converted Freqtrade result with:

```text
Trades: 230
Win rate: 41.3043%
Total return: -15.542%
Max drawdown: 24.4939%
Profit factor: 0.8107
```

This is a process pass, not a Dry-run approval. The strategy result is negative,
so the next step is backtest diagnosis rather than Dry-run.

## Missing Metrics

If Freqtrade does not provide a metric, V13.4 uses `null` rather than inventing
values. The missing field is explained in `reportWarnings` when possible.

## Safety Boundary

Report export reads local files only. It does not use API keys, does not call
exchange private APIs, and does not place orders.
