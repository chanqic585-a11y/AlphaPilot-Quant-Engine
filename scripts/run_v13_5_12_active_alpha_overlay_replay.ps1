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
  "alphapilot.reports.generate_v13_5_12_active_alpha_overlay_replay_report",
  "--output-report",
  "reports/v13_5_12_active_alpha_overlay_replay_report.json",
  "--output-summary",
  "reports/v13_5_12_active_alpha_overlay_replay_summary.md",
  "--output-signal-log",
  "reports/v13_5_12_active_alpha_overlay_signal_log.json",
  "--output-ledger",
  "reports/v13_5_12_active_alpha_overlay_paper_ledger.json"
)

Write-Host "AlphaPilot V13.5.12 Active Alpha Overlay Replay"
Write-Host "Historical replay only. Not forward validation, exchange Dry-run, or live trading."
Write-Host "$pythonExe $($cmd -join ' ')"

if ($Run) {
  & $pythonExe @cmd
  if ($LASTEXITCODE -ne 0) {
    throw "V13.5.12 active alpha overlay replay failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. Add -Run to generate reports."
}
