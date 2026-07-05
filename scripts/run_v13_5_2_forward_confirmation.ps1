param(
  [double]$ConfirmationFraction = 0.30,
  [switch]$Run
)

$report = "reports/v13_5_2_forward_confirmation_report.json"
$summary = "reports/v13_5_2_forward_confirmation_summary.md"
$signals = "reports/v13_5_2_forward_confirmation_signal_log.json"

$pythonArgs = @(
  "-m",
  "alphapilot.reports.generate_v13_5_2_forward_confirmation_report",
  "--confirmation-fraction",
  "$ConfirmationFraction",
  "--output-report",
  $report,
  "--output-summary",
  $summary,
  "--output-signals",
  $signals
)

Write-Host "AlphaPilot V13.5.2 forward-confirmation command:"
Write-Host ("python " + ($pythonArgs -join " "))
Write-Host "Research only. Local paper sandbox is local simulated observation only."
Write-Host "No exchange Dry-run, no live trading, no API keys, no private endpoints, no orders."
Write-Host "Default mode is preview only. Add -Run to execute."

if ($Run) {
  & python @pythonArgs
} else {
  Write-Host "Preview only. No report was generated."
}
