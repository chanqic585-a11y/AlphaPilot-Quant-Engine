param(
  [string]$ReportTimeframes = "1h,4h",
  [string]$Pairs = "",
  [switch]$Run
)

$ErrorActionPreference = "Stop"

Write-Host "AlphaPilot V13.5.6 high reward event redesign"
Write-Host "Report timeframes: $ReportTimeframes"
Write-Host "Pairs: $(if ($Pairs) { $Pairs } else { 'discover local pairs' })"
Write-Host "Default mode is preview only. Add -Run to execute."

if (-not $Run) {
  Write-Host "Preview command:"
  Write-Host "powershell -ExecutionPolicy Bypass -File scripts/run_v13_5_6_high_reward_event_redesign.ps1 -Run"
  exit 0
}

$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$PythonExe = "python"
if (Test-Path $BundledPython) {
  $PythonExe = $BundledPython
}

$reportArgs = @(
  "-m",
  "alphapilot.reports.generate_v13_5_6_high_reward_event_redesign_report",
  "--timeframes",
  $ReportTimeframes,
  "--output-report",
  "reports/v13_5_6_high_reward_event_redesign_report.json",
  "--output-summary",
  "reports/v13_5_6_high_reward_event_redesign_summary.md",
  "--output-candidates",
  "reports/v13_5_6_high_reward_candidates.json"
)

if ($Pairs) {
  $reportArgs += "--pairs"
  $reportArgs += $Pairs
}

& $PythonExe @reportArgs

if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
