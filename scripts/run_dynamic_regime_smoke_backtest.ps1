param(
  [string]$Pairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT",
  [string]$Timerange = "20260401-",
  [string]$Timeframe = "1h",
  [switch]$Run
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "run_backtest.ps1"
$argsList = @(
  "-Strategy",
  "AlphaPilotDynamicRegimeV01",
  "-Timeframe",
  $Timeframe,
  "-Timerange",
  $Timerange,
  "-Pairs",
  $Pairs
)

if ($Run) {
  $argsList += "-Run"
}

Write-Host "AlphaPilot V13.4.16 Dynamic Regime smoke backtest wrapper"
Write-Host "Pairs: $Pairs"
Write-Host "Timerange: $Timerange"
Write-Host "Timeframe: $Timeframe"
Write-Host "This wrapper runs a local Freqtrade backtest only. It does not enter Dry-run or live trading."

& powershell -ExecutionPolicy Bypass -File $scriptPath @argsList

