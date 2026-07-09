param(
  [string]$DataDir = "user_data/data/local5m/okx",
  [string]$Timerange = "20180101-",
  [string]$Pairs = "",
  [int]$MaxPairs = 0,
  [int]$PairChunkSize = 20,
  [int]$MaxChunks = 0,
  [string]$Strategies = "all",
  [switch]$Resume,
  [switch]$Run
)

$ErrorActionPreference = "Stop"

$pythonArgs = @(
  "-m",
  "alphapilot.backtesting.external_5m_batch_runner",
  "--data-dir",
  $DataDir,
  "--timerange",
  $Timerange,
  "--pair-chunk-size",
  [string]$PairChunkSize,
  "--strategies",
  $Strategies
)

if ($Pairs) {
  $pythonArgs += @("--pairs", $Pairs)
}
if ($MaxPairs -gt 0) {
  $pythonArgs += @("--max-pairs", [string]$MaxPairs)
}
if ($MaxChunks -gt 0) {
  $pythonArgs += @("--max-chunks", [string]$MaxChunks)
}
if ($Run) {
  $pythonArgs += "--run"
}
if ($Resume) {
  $pythonArgs += "--resume"
}

Write-Host "AlphaPilot external 5m all-strategy backtest"
Write-Host "DataDir: $DataDir"
Write-Host "Timerange: $Timerange"
Write-Host "Pairs: $(if ($Pairs) { $Pairs } elseif ($MaxPairs -gt 0) { "first $MaxPairs imported pairs" } else { "all imported pairs" })"
Write-Host "PairChunkSize: $PairChunkSize"
Write-Host "MaxChunks: $(if ($MaxChunks -gt 0) { $MaxChunks } else { "all chunks" })"
Write-Host "Strategies: $Strategies"
Write-Host "Resume: $(if ($Resume) { "enabled" } else { "disabled" })"
Write-Host "Research backtest only. No Dry-run, no live trading, no private API, no orders."
python @pythonArgs
