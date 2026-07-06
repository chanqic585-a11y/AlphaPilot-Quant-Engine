param(
  [switch]$Run,
  [string]$Exchanges = "okx,binance,bybit",
  [int]$MaxPairs = 0
)

$ErrorActionPreference = "Stop"

$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$pythonExe = "python"
if (Test-Path $BundledPython) {
  $pythonExe = $BundledPython
}

$cmd = @(
  "-m",
  "alphapilot.reports.generate_v13_5_23_alpha191_crypto_subset_replay_report",
  "--data-root",
  "user_data/data",
  "--exchanges",
  $Exchanges,
  "--max-pairs",
  "$MaxPairs",
  "--output-report",
  "reports/v13_5_23_alpha191_crypto_subset_replay_report.json",
  "--output-summary",
  "reports/v13_5_23_alpha191_crypto_subset_replay_summary.md",
  "--output-signal-log",
  "reports/v13_5_23_alpha191_crypto_subset_signal_log.json",
  "--output-selected",
  "reports/v13_5_23_alpha191_crypto_subset_selected_signals.json"
)

Write-Host "AlphaPilot V13.5.23 Alpha191 Crypto-Safe Subset Replay"
Write-Host "Research replay only. No formulas copied, no orders, no API keys, no auto trading."
Write-Host "$pythonExe $($cmd -join ' ')"

if ($Run) {
  & $pythonExe @cmd
  if ($LASTEXITCODE -ne 0) {
    throw "V13.5.23 Alpha191 subset replay failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. Add -Run to generate reports."
}
