param(
  [switch]$Run,
  [int]$MaxConcurrentPositions = 8
)

$ErrorActionPreference = "Stop"

$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$pythonExe = "python"
if (Test-Path $BundledPython) {
  $pythonExe = $BundledPython
}

$cmd = @(
  "-m",
  "alphapilot.reports.generate_v13_5_21_local_paper_refresh_candidate_report",
  "--max-concurrent-positions",
  "$MaxConcurrentPositions",
  "--output-report",
  "reports/v13_5_21_local_paper_refresh_candidate_report.json",
  "--output-summary",
  "reports/v13_5_21_local_paper_refresh_candidate_summary.md",
  "--output-ledger",
  "reports/v13_5_21_local_paper_refresh_candidate_ledger.json",
  "--output-package",
  "reports/v13_5_21_local_paper_refresh_candidate_package.json"
)

Write-Host "AlphaPilot V13.5.21 Local Paper Refresh Candidate"
Write-Host "Local simulation only. Uses V13.5.20 selected signals. No orders, no API keys, no auto trading."
Write-Host "$pythonExe $($cmd -join ' ')"

if ($Run) {
  & $pythonExe @cmd
  if ($LASTEXITCODE -ne 0) {
    throw "V13.5.21 local paper refresh candidate failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. Add -Run to generate reports."
}
