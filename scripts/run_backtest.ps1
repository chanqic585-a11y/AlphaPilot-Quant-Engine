param(
  [string]$Timerange = "20240101-20240701",
  [string]$Pairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT",
  [string]$Strategy = "AlphaPilotVolumeReboundV01",
  [string]$Timeframe = "15m",
  [switch]$Smoke,
  [switch]$UseTop30,
  [switch]$Run
)

function Split-CsvArg {
  param([string]$Value)
  return $Value.Split(",") |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_.Length -gt 0 }
}

function Get-Top30Pairs {
  return @(
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "DOGE/USDT:USDT",
    "XRP/USDT:USDT",
    "ADA/USDT:USDT",
    "AVAX/USDT:USDT",
    "LINK/USDT:USDT",
    "SUI/USDT:USDT",
    "APT/USDT:USDT",
    "OP/USDT:USDT",
    "ARB/USDT:USDT",
    "LTC/USDT:USDT",
    "BCH/USDT:USDT",
    "DOT/USDT:USDT",
    "NEAR/USDT:USDT",
    "PEPE/USDT:USDT",
    "WIF/USDT:USDT",
    "ORDI/USDT:USDT",
    "TON/USDT:USDT",
    "INJ/USDT:USDT",
    "FIL/USDT:USDT",
    "ETC/USDT:USDT",
    "TRX/USDT:USDT",
    "UNI/USDT:USDT",
    "AAVE/USDT:USDT",
    "ATOM/USDT:USDT",
    "SEI/USDT:USDT",
    "TIA/USDT:USDT",
    "FET/USDT:USDT"
  )
}

if ($Smoke) {
  $Pairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT"
}

$pairList = if ($UseTop30 -and -not $Smoke) {
  @(Get-Top30Pairs)
} else {
  @(Split-CsvArg $Pairs)
}
$exportFile = "user_data/backtest_results/alphapilot_v13_4_backtest.json"

$dockerArgs = @(
  "compose",
  "run",
  "--rm",
  "freqtrade",
  "backtesting",
  "--config",
  "user_data/config/config.backtest.json",
  "--strategy",
  $Strategy,
  "--timerange",
  $Timerange,
  "--timeframe",
  $Timeframe,
  "--fee",
  "0.0005",
  "--export",
  "trades",
  "--export-filename",
  $exportFile,
  "--pairs"
) + $pairList

$commandPreview = "docker " + ($dockerArgs -join " ")

Write-Host "AlphaPilot V13.4 backtest command:"
Write-Host $commandPreview
Write-Host "Pairs: $($pairList -join ', ')"
Write-Host "Timerange: $Timerange"
Write-Host "Strategy: $Strategy"
Write-Host "Timeframe: $Timeframe"
Write-Host "Fee model: 0.05% one-way via --fee 0.0005"
Write-Host "Slippage model: planned in report schema; not applied by Freqtrade command yet."
Write-Host "Default mode is preview only. Add -Run to execute Docker."

if ($Run) {
  & docker @dockerArgs
} else {
  Write-Host "Dry preview only. No backtest was executed."
}
