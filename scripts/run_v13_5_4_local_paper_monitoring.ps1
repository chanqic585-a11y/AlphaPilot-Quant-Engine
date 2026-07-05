param(
  [switch]$RefreshPublicData,
  [string]$RefreshTimerange = "20260704-",
  [string]$RefreshPairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT,DOGE/USDT:USDT,XRP/USDT:USDT,ADA/USDT:USDT,AVAX/USDT:USDT,LINK/USDT:USDT,SUI/USDT:USDT,APT/USDT:USDT,OP/USDT:USDT,ARB/USDT:USDT,LTC/USDT:USDT,BCH/USDT:USDT,DOT/USDT:USDT,NEAR/USDT:USDT,PEPE/USDT:USDT,WIF/USDT:USDT,ORDI/USDT:USDT,INJ/USDT:USDT,FIL/USDT:USDT,ETC/USDT:USDT,UNI/USDT:USDT,AAVE/USDT:USDT,ATOM/USDT:USDT,SEI/USDT:USDT,TIA/USDT:USDT",
  [switch]$Run
)

$forwardArgs = @(
  "-m",
  "alphapilot.reports.generate_v13_5_2_forward_confirmation_report",
  "--confirmation-fraction",
  "0.30",
  "--output-report",
  "reports/v13_5_2_forward_confirmation_report.json",
  "--output-summary",
  "reports/v13_5_2_forward_confirmation_summary.md",
  "--output-signals",
  "reports/v13_5_2_forward_confirmation_signal_log.json"
)

$ledgerArgs = @(
  "-m",
  "alphapilot.reports.generate_v13_5_3_local_paper_sandbox_report",
  "--initial-equity",
  "10000",
  "--risk-per-signal-pct",
  "1",
  "--max-concurrent-positions",
  "8",
  "--max-notional-per-signal-pct",
  "35",
  "--output-ledger",
  "reports/v13_5_3_local_paper_sandbox_ledger.json",
  "--output-report",
  "reports/v13_5_3_local_paper_sandbox_report.json",
  "--output-summary",
  "reports/v13_5_3_local_paper_sandbox_summary.md"
)

$monitorArgs = @(
  "-m",
  "alphapilot.reports.generate_v13_5_4_local_paper_monitoring_report",
  "--signal-log",
  "reports/v13_5_2_forward_confirmation_signal_log.json",
  "--ledger",
  "reports/v13_5_3_local_paper_sandbox_ledger.json",
  "--ledger-report",
  "reports/v13_5_3_local_paper_sandbox_report.json",
  "--output-report",
  "reports/v13_5_4_local_paper_monitoring_report.json",
  "--output-summary",
  "reports/v13_5_4_local_paper_monitoring_summary.md",
  "--output-events",
  "reports/v13_5_4_local_paper_monitoring_events.json"
)

Write-Host "AlphaPilot V13.5.4 local paper monitoring pipeline"
Write-Host "Local simulation monitoring only. No exchange Dry-run, no live trading, no API keys, no private endpoints, no orders."
Write-Host "Refresh public data: $RefreshPublicData"
Write-Host "Refresh timerange: $RefreshTimerange"
Write-Host "Default mode is preview only. Add -Run to execute."
Write-Host ""
if ($RefreshPublicData) {
  Write-Host "Public data refresh command:"
  Write-Host "powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -Pairs `"$RefreshPairs`" -Timeframes `"1h`" -Timerange `"$RefreshTimerange`" -Run"
}
Write-Host "Forward confirmation command:"
Write-Host ("python " + ($forwardArgs -join " "))
Write-Host "Local paper ledger command:"
Write-Host ("python " + ($ledgerArgs -join " "))
Write-Host "Monitoring report command:"
Write-Host ("python " + ($monitorArgs -join " "))

if ($Run) {
  if ($RefreshPublicData) {
    powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -Pairs $RefreshPairs -Timeframes "1h" -Timerange $RefreshTimerange -Run
    if ($LASTEXITCODE -ne 0) {
      throw "Public data refresh failed with exit code $LASTEXITCODE"
    }
  }
  & python @forwardArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Forward confirmation failed with exit code $LASTEXITCODE"
  }
  & python @ledgerArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Local paper ledger failed with exit code $LASTEXITCODE"
  }
  & python @monitorArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Local paper monitoring failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. No data refresh or reports were generated."
}
