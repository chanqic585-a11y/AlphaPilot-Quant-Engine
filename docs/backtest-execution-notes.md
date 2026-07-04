# Backtest Execution Notes

V13.3 prepares baseline backtest execution. Scripts default to dry preview and
only execute Docker commands when `-Run` is explicitly supplied.

## Smoke Backtest

Recommended first run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" -Timeframes "15m,1h,4h" -Timerange "20240101-"
powershell -ExecutionPolicy Bypass -File scripts/run_backtest.ps1 -Smoke -Timerange "20240101-20240701"
```

Then re-run each command with `-Run` only after verifying Docker Desktop and the
Freqtrade image are available.

## Top 30 Backtest

Use the fixed Top 30 universe in `alphapilot/universe/top30_usdt_swap.py`.
V13.3 intentionally avoids dynamic hot lists to reduce historical selection
bias.

Example command preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_backtest.ps1 -Timerange "20240101-20240701"
```

## Report Export

```powershell
python -m alphapilot.reports.export_backtest_report
```

Behavior:

- If a Freqtrade JSON result exists, export `reports/latest_backtest_report.json`
  with `isMock=false`.
- If no result exists, export `reports/sample_backtest_report.json` with
  `isMock=true`.

## Current Limitations

- Slippage is documented and reserved in the report schema, but not yet applied
  by the Freqtrade backtest command.
- Skipped-signal counts are schema placeholders in V13.3.
- Docker / Freqtrade execution depends on the local environment and may need a
  separate setup check.

## Safety Boundary

V13.3 is research and backtesting only. It does not enable live trading, real
API keys, account reads, position reads, real orders, or automatic trading.
