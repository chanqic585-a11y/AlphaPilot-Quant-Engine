# Backtest Runtime Troubleshooting

This guide records V13.4 runtime checks for real Freqtrade smoke backtests.

## Docker Not Found

Symptom:

```text
docker : The term 'docker' is not recognized as the name of a cmdlet...
```

Action:

1. Install Docker Desktop.
2. Start Docker Desktop.
3. Open a new PowerShell window.
4. Run:

```powershell
docker --version
docker compose version
```

Do not tag V13.4 until Docker is available and the smoke backtest succeeds.

## Data Download Fails

Check:

- Pair format uses OKX futures format, for example `BTC/USDT:USDT`.
- Config uses `trading_mode = futures`.
- Config uses `margin_mode = isolated`.
- The command is run from `D:\Codex-Workspace\AlphaPilot-Quant-Engine`.

## Backtest Fails

Allowed fixes in V13.4:

- Freqtrade API compatibility issues.
- Informative pair merge runtime issues.
- Pair formatting issues.
- Config field compatibility issues.
- Script argument quoting issues.
- Report export lookup issues.

Not allowed in V13.4:

- Changing stoploss because results are poor.
- Changing take profit because results are poor.
- Changing RSI or volumeRatio thresholds because signal count is low.
- Adding live trading or real API keys.

## Report Export Fails

Run:

```powershell
python -m alphapilot.reports.export_backtest_report
```

If no Freqtrade result exists, the report must remain `isMock=true`.
If a real Freqtrade result exists, the report exporter should produce
`reports/latest_backtest_report.json` and `reports/smoke_backtest_report.json`
with `isMock=false`.
