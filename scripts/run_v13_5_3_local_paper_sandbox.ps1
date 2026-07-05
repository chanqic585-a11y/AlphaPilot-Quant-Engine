param(
  [double]$InitialEquity = 10000,
  [double]$RiskPerSignalPct = 1.0,
  [int]$MaxConcurrentPositions = 8,
  [double]$MaxNotionalPerSignalPct = 35.0,
  [switch]$Run
)

$ledger = "reports/v13_5_3_local_paper_sandbox_ledger.json"
$report = "reports/v13_5_3_local_paper_sandbox_report.json"
$summary = "reports/v13_5_3_local_paper_sandbox_summary.md"

$pythonArgs = @(
  "-m",
  "alphapilot.reports.generate_v13_5_3_local_paper_sandbox_report",
  "--initial-equity",
  "$InitialEquity",
  "--risk-per-signal-pct",
  "$RiskPerSignalPct",
  "--max-concurrent-positions",
  "$MaxConcurrentPositions",
  "--max-notional-per-signal-pct",
  "$MaxNotionalPerSignalPct",
  "--output-ledger",
  $ledger,
  "--output-report",
  $report,
  "--output-summary",
  $summary
)

Write-Host "AlphaPilot V13.5.3 local paper sandbox command:"
Write-Host ("python " + ($pythonArgs -join " "))
Write-Host "Local simulation only. No exchange Dry-run, no live trading, no API keys, no private endpoints, no orders."
Write-Host "Default mode is preview only. Add -Run to execute."

if ($Run) {
  & python @pythonArgs
} else {
  Write-Host "Preview only. No report was generated."
}
