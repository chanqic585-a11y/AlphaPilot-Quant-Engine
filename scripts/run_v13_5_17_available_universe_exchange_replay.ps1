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
  "alphapilot.reports.generate_v13_5_17_available_universe_exchange_replay_report",
  "--output-report",
  "reports/v13_5_17_available_universe_exchange_replay_report.json",
  "--output-summary",
  "reports/v13_5_17_available_universe_exchange_replay_summary.md",
  "--output-signal-log",
  "reports/v13_5_17_available_universe_exchange_signal_log.json"
)

Write-Host "AlphaPilot V13.5.17 Available-Universe Exchange Replay"
Write-Host "Uses only local public data files already present. Fixed active pool, no tuning."
Write-Host "No Trade API, no Withdraw API, no API key storage, no orders, no auto trading."
Write-Host "$pythonExe $($cmd -join ' ')"

if ($Run) {
  & $pythonExe @cmd
  if ($LASTEXITCODE -ne 0) {
    throw "V13.5.17 available-universe exchange replay failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. Add -Run to generate reports."
}
