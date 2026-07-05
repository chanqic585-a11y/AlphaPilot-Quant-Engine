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
  "alphapilot.reports.generate_v13_5_15_multi_exchange_data_coverage_report",
  "--output-report",
  "reports/v13_5_15_multi_exchange_data_coverage_report.json",
  "--output-summary",
  "reports/v13_5_15_multi_exchange_data_coverage_summary.md"
)

Write-Host "AlphaPilot V13.5.15 Multi-Exchange Data Coverage"
Write-Host "Local public historical data coverage audit only."
Write-Host "No Trade API, no Withdraw API, no API key storage, no orders, no auto trading."
Write-Host "$pythonExe $($cmd -join ' ')"

if ($Run) {
  & $pythonExe @cmd
  if ($LASTEXITCODE -ne 0) {
    throw "V13.5.15 multi-exchange data coverage report failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. Add -Run to generate reports."
}
