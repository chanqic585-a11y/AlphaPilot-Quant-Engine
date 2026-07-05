param(
  [string]$Pairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT",
  [ValidateSet("1h", "4h")]
  [string]$Timeframe = "4h",
  [int]$Folds = 5,
  [switch]$Run
)

$report = if ($Timeframe -eq "1h") {
  "reports/v13_5_derivatives_ml_strategy_1h_report.json"
} else {
  "reports/v13_5_derivatives_ml_strategy_4h_report.json"
}
$summary = if ($Timeframe -eq "1h") {
  "reports/v13_5_derivatives_ml_strategy_1h_summary.md"
} else {
  "reports/v13_5_derivatives_ml_strategy_4h_summary.md"
}
$signals = if ($Timeframe -eq "1h") {
  "reports/v13_5_derivatives_ml_1h_shadow_signals_sample.json"
} else {
  "reports/v13_5_derivatives_ml_4h_shadow_signals_sample.json"
}

$pythonArgs = @(
  "-m",
  "alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report",
  "--timeframe",
  $Timeframe,
  "--pairs",
  $Pairs,
  "--folds",
  "$Folds",
  "--output-report",
  $report,
  "--output-summary",
  $summary,
  "--output-signals",
  $signals
)

Write-Host "AlphaPilot V13.5 derivatives ML-gated research command:"
Write-Host ("python " + ($pythonArgs -join " "))
Write-Host "Research only. No Dry-run, no live trading, no API keys, no private endpoints, no orders."
Write-Host "Default mode is preview only. Add -Run to execute."

if ($Run) {
  & python @pythonArgs
} else {
  Write-Host "Preview only. No report was generated."
}
