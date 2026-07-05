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
  "alphapilot.reports.generate_v13_5_10_continuous_learning_loop_report",
  "--output-report",
  "reports/v13_5_10_continuous_learning_loop_report.json",
  "--output-summary",
  "reports/v13_5_10_continuous_learning_loop_summary.md",
  "--output-dataset",
  "reports/v13_5_10_strategy_evolution_dataset.json",
  "--output-state",
  "reports/v13_5_10_learning_state.json"
)

Write-Host "AlphaPilot V13.5.10 Continuous Learning Loop"
Write-Host "Research only. Converts local paper outcomes into learning samples; no retraining or orders."
Write-Host "$pythonExe $($cmd -join ' ')"

if ($Run) {
  & $pythonExe @cmd
  if ($LASTEXITCODE -ne 0) {
    throw "V13.5.10 continuous learning loop failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. Add -Run to generate reports."
}
