param(
  [string]$DataPath = "user_data/data/okx/futures",
  [string]$Timerange = "20260101-",
  [string]$Timeframes = "15m,30m,1h",
  [int]$MaxSelected = 5,
  [int]$MaxPairsPerTimeframe = 0
)

$ErrorActionPreference = "Stop"

$pythonArgs = @(
  "-m",
  "alphapilot.reports.generate_v13_7_40_short_cycle_parameter_search",
  "--data-path",
  $DataPath,
  "--timerange",
  $Timerange,
  "--timeframes",
  $Timeframes,
  "--max-selected",
  "$MaxSelected"
)

if ($MaxPairsPerTimeframe -gt 0) {
  $pythonArgs += @("--max-pairs-per-timeframe", "$MaxPairsPerTimeframe")
}

Write-Host "AlphaPilot V13.7.40 short-cycle parameter search"
Write-Host "DataPath: $DataPath"
Write-Host "Timerange: $Timerange"
Write-Host "Timeframes: $Timeframes"
Write-Host "MaxSelected: $MaxSelected"
Write-Host "Exchange/private endpoints: disabled"
Write-Host "Orders/live trading: disabled"

python @pythonArgs
