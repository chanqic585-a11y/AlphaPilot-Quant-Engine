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
  "alphapilot.reports.generate_v13_5_13_forward_readiness_monitor",
  "--output-report",
  "reports/v13_5_13_forward_readiness_monitor_report.json",
  "--output-summary",
  "reports/v13_5_13_forward_readiness_monitor_summary.md"
)

Write-Host "AlphaPilot V13.5.13 Forward Readiness Monitor"
Write-Host "Checks post-selection candle availability. No exchange execution."
Write-Host "$pythonExe $($cmd -join ' ')"

if ($Run) {
  & $pythonExe @cmd
  if ($LASTEXITCODE -ne 0) {
    throw "V13.5.13 forward readiness monitor failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. Add -Run to generate reports."
}
