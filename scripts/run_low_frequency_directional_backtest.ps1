param(
  [string]$Timerange = "20240101-",
  [string]$Pairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT",
  [switch]$Run
)

$ErrorActionPreference = "Stop"

function Split-CsvArg {
  param([string]$Value)
  return $Value.Split(",") |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_.Length -gt 0 }
}

$pairList = @(Split-CsvArg $Pairs)
$strategy = "AlphaPilotLowFrequencyDirectional4HV01"
$timeframe = "4h"
$exportFile = "user_data/backtest_results/v13_4_34_low_frequency_directional_4h.zip"

$dockerArgs = @(
  "compose",
  "run",
  "--rm",
  "freqtrade",
  "backtesting",
  "--config",
  "user_data/config/config.backtest.json",
  "--strategy",
  $strategy,
  "--timerange",
  $Timerange,
  "--timeframe",
  $timeframe,
  "--fee",
  "0.0005",
  "--export",
  "trades",
  "--export-filename",
  $exportFile,
  "--pairs"
) + $pairList

$commandPreview = "docker " + ($dockerArgs -join " ")

Write-Host "AlphaPilot V13.4.34 low-frequency directional research backtest command:"
Write-Host $commandPreview
Write-Host "Pairs: $($pairList -join ', ')"
Write-Host "Timerange: $Timerange"
Write-Host "Strategy: $strategy"
Write-Host "Timeframe: $timeframe"
Write-Host "Fee model: 0.05% one-way via --fee 0.0005"
Write-Host "Slippage model: post-processing only; not applied by Freqtrade."
Write-Host "This is research backtest only. No Dry-run, no live trading, no private API, no orders."
Write-Host "Default mode is preview only. Add -Run to execute Docker."

if ($Run) {
  & docker @dockerArgs
  $lastResultPath = "user_data/backtest_results/.last_result.json"
  if (Test-Path $lastResultPath) {
    $lastResult = Get-Content $lastResultPath -Raw | ConvertFrom-Json
    if ($lastResult.latest_backtest) {
      $latestPath = Join-Path "user_data/backtest_results" $lastResult.latest_backtest
      if ((Test-Path $latestPath) -and ($latestPath -ne $exportFile)) {
        Copy-Item -LiteralPath $latestPath -Destination $exportFile -Force
        Write-Host "Copied latest Freqtrade result to $exportFile"
      }
    }
  }
} else {
  Write-Host "Preview only. No backtest was executed."
}

