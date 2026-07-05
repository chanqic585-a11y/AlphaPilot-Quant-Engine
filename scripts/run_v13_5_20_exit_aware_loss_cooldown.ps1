param(
  [switch]$Run
)

$ErrorActionPreference = "Stop"

$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$pythonExe = "python"
if (Test-Path $BundledPython) {
  $pythonExe = $BundledPython
}

$cmd = @(
  "-m",
  "alphapilot.reports.generate_v13_5_20_exit_aware_loss_cooldown_report",
  "--output-report",
  "reports/v13_5_20_exit_aware_loss_cooldown_report.json",
  "--output-summary",
  "reports/v13_5_20_exit_aware_loss_cooldown_summary.md",
  "--output-selected",
  "reports/v13_5_20_best_exit_aware_policy_selected_signals.json"
)

Write-Host "AlphaPilot V13.5.20 Exit-Aware Loss Cooldown"
Write-Host "Loss cooldown starts after exitDate only. No future leakage, no entry tuning, 2R target unchanged."
Write-Host "No Trade API, no Withdraw API, no API key storage, no orders, no auto trading."
Write-Host "$pythonExe $($cmd -join ' ')"

if ($Run) {
  & $pythonExe @cmd
  if ($LASTEXITCODE -ne 0) {
    throw "V13.5.20 exit-aware loss cooldown failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. Add -Run to generate reports."
}
