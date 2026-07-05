param(
  [string]$Pairs = "",
  [ValidateSet("1h", "4h")]
  [string]$Timeframe = "1h",
  [int]$Folds = 5,
  [int]$MaxConfigs = 0,
  [switch]$Run
)

$suffix = if ($Timeframe -eq "1h") { "1h" } else { "4h" }
$report = "reports/v13_5_1_expanded_relaxed_${suffix}_report.json"
$summary = "reports/v13_5_1_expanded_relaxed_${suffix}_summary.md"
$signals = "reports/v13_5_1_relaxed_${suffix}_shadow_watchlist_sample.json"

$pythonArgs = @(
  "-m",
  "alphapilot.reports.generate_v13_5_1_expanded_relaxed_research_report",
  "--timeframe",
  $Timeframe,
  "--folds",
  "$Folds",
  "--output-report",
  $report,
  "--output-summary",
  $summary,
  "--output-signals",
  $signals
)

if ($Pairs.Trim().Length -gt 0) {
  $pythonArgs += @("--pairs", $Pairs)
}

if ($MaxConfigs -gt 0) {
  $pythonArgs += @("--max-configs", "$MaxConfigs")
}

Write-Host "AlphaPilot V13.5.1 expanded relaxed derivatives research command:"
Write-Host ("python " + ($pythonArgs -join " "))
Write-Host "Research only. Relaxed candidates are shadow-watchlist only."
Write-Host "No Dry-run, no live trading, no API keys, no private endpoints, no orders."
Write-Host "If Pairs is empty, the script auto-discovers local futures data for the selected timeframe."
Write-Host "Default mode is preview only. Add -Run to execute."

if ($Run) {
  & python @pythonArgs
} else {
  Write-Host "Preview only. No report was generated."
}
