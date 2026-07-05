param(
  [string]$ReportTimeframes = "1h,4h",
  [string]$Pairs = "",
  [switch]$Run
)

$ErrorActionPreference = "Stop"

Write-Host "AlphaPilot V13.5.7 external Alpha101-style overlay research"
Write-Host "Report timeframes: $ReportTimeframes"
Write-Host "Pairs: $(if ($Pairs) { $Pairs } else { 'discover local pairs' })"
Write-Host "Default mode is preview only. Add -Run to execute."

if (-not $Run) {
  Write-Host "Preview command:"
  Write-Host "powershell -ExecutionPolicy Bypass -File scripts/run_v13_5_7_external_alpha_overlay.ps1 -Run"
  exit 0
}

$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$PythonExe = "python"
if (Test-Path $BundledPython) {
  $PythonExe = $BundledPython
}

$reportArgs = @(
  "-m",
  "alphapilot.reports.generate_v13_5_7_external_alpha_overlay_report",
  "--timeframes",
  $ReportTimeframes,
  "--output-report",
  "reports/v13_5_7_external_alpha_overlay_report.json",
  "--output-summary",
  "reports/v13_5_7_external_alpha_overlay_summary.md",
  "--output-candidates",
  "reports/v13_5_7_alpha_overlay_candidates.json"
)

if ($Pairs) {
  $reportArgs += "--pairs"
  $reportArgs += $Pairs
}

& $PythonExe @reportArgs

if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
