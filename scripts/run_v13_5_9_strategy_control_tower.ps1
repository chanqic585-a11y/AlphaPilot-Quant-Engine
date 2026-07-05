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
  "alphapilot.reports.generate_v13_5_9_strategy_control_tower_report",
  "--output-report",
  "reports/v13_5_9_strategy_control_tower_report.json",
  "--output-summary",
  "reports/v13_5_9_strategy_control_tower_summary.md",
  "--output-router-intents",
  "reports/v13_5_9_local_paper_router_intents.json",
  "--output-reference-index",
  "reports/v13_5_9_external_reference_index.json"
)

Write-Host "AlphaPilot V13.5.9 Strategy Control Tower"
Write-Host "Research only. Local paper router intents are not orders."
Write-Host "$pythonExe $($cmd -join ' ')"

if ($Run) {
  & $pythonExe @cmd
  if ($LASTEXITCODE -ne 0) {
    throw "V13.5.9 strategy control tower failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. Add -Run to generate reports."
}
