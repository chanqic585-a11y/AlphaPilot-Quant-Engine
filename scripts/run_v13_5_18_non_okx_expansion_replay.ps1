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
  "alphapilot.reports.generate_v13_5_18_non_okx_expansion_replay_report",
  "--output-report",
  "reports/v13_5_18_non_okx_expansion_replay_report.json",
  "--output-summary",
  "reports/v13_5_18_non_okx_expansion_replay_summary.md",
  "--output-signal-log",
  "reports/v13_5_18_non_okx_expansion_signal_log.json"
)

Write-Host "AlphaPilot V13.5.18 Non-OKX Expansion Replay"
Write-Host "Post-download replay report only. Fixed active pool, no tuning."
Write-Host "No Trade API, no Withdraw API, no API key storage, no orders, no auto trading."
Write-Host "$pythonExe $($cmd -join ' ')"

if ($Run) {
  & $pythonExe @cmd
  if ($LASTEXITCODE -ne 0) {
    throw "V13.5.18 non-OKX expansion replay failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. Add -Run to generate reports."
}
