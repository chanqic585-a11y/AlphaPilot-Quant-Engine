param(
  [string]$BacktestReport = "reports/v13_4_smoke_backtest_report.json",
  [string]$OutputJson = "reports/v13_4_2_signal_audit_report.json",
  [string]$OutputSummary = "reports/v13_4_2_signal_audit_summary.md"
)

$pythonArgs = @(
  "-m",
  "alphapilot.reports.generate_signal_audit_report",
  "--backtest-report",
  $BacktestReport,
  "--output-json",
  $OutputJson,
  "--output-summary",
  $OutputSummary
)

$pythonCommand = if ($env:PYTHON) { $env:PYTHON } else { "python" }

Write-Host "AlphaPilot V13.4.2 signal audit command:"
Write-Host ($pythonCommand + " " + ($pythonArgs -join " "))
Write-Host "This reads local backtest/OHLCV files only. It does not enter Dry-run or place orders."

& $pythonCommand @pythonArgs
