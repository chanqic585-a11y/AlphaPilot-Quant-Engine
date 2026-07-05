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
  "alphapilot.reports.generate_v13_5_16_core_multi_exchange_replay_report",
  "--output-report",
  "reports/v13_5_16_core_multi_exchange_replay_report.json",
  "--output-summary",
  "reports/v13_5_16_core_multi_exchange_replay_summary.md",
  "--output-signal-log",
  "reports/v13_5_16_core_multi_exchange_signal_log.json"
)

Write-Host "AlphaPilot V13.5.16 Core Multi-Exchange Replay"
Write-Host "Historical public-data replay only. Fixed active pool, no strategy tuning."
Write-Host "No Trade API, no Withdraw API, no API key storage, no orders, no auto trading."
Write-Host "$pythonExe $($cmd -join ' ')"

if ($Run) {
  & $pythonExe @cmd
  if ($LASTEXITCODE -ne 0) {
    throw "V13.5.16 core multi-exchange replay failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. Add -Run to generate reports."
}
