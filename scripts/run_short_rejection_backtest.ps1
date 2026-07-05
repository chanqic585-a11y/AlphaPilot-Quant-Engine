param(
  [switch]$Smoke,
  [switch]$Expanded,
  [string]$Timerange = "",
  [string]$Pairs = "",
  [switch]$UseSupportedPairs,
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

function Get-SupportedPairs {
  return @(Get-Top30Pairs) | Where-Object {
    $_ -notin @("FET/USDT:USDT", "TON/USDT:USDT")
  }
}

if (-not $Smoke -and -not $Expanded) {
  $Smoke = $true
}

if ($Smoke) {
  if ([string]::IsNullOrWhiteSpace($Timerange)) {
    $Timerange = "20260401-"
  }
  if ([string]::IsNullOrWhiteSpace($Pairs)) {
    $Pairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT"
  }
  $pairList = @(Split-CsvArg $Pairs)
  $scope = "smoke"
} elseif ($Expanded) {
  if ([string]::IsNullOrWhiteSpace($Timerange)) {
    $Timerange = "20260101-"
  }
  $pairList = if ($UseSupportedPairs -or [string]::IsNullOrWhiteSpace($Pairs)) {
    @(Get-SupportedPairs)
  } else {
    @(Split-CsvArg $Pairs)
  }
  $scope = "expanded"
}

$exportFile = "user_data/backtest_results/alphapilot_v13_4_29_short_rejection_1h_$scope.json"

$dockerArgs = @(
  "compose",
  "run",
  "--rm",
  "freqtrade",
  "backtesting",
  "--config",
  "user_data/config/config.backtest.json",
  "--strategy",
  "AlphaPilotShortRejection1HV01",
  "--timerange",
  $Timerange,
  "--timeframe",
  "1h",
  "--fee",
  "0.0005",
  "--export",
  "trades",
  "--export-filename",
  $exportFile,
  "--pairs"
) + $pairList

$commandPreview = "docker " + ($dockerArgs -join " ")

Write-Host "AlphaPilot V13.4.29 Short Rejection 1H backtest command:"
Write-Host $commandPreview
Write-Host "Scope: $scope"
Write-Host "Pairs: $($pairList -join ', ')"
Write-Host "Timerange: $Timerange"
Write-Host "Strategy: AlphaPilotShortRejection1HV01"
Write-Host "Timeframe: 1h"
Write-Host "Fee model: 0.05% one-way via --fee 0.0005"
Write-Host "Slippage model: report-layer post-processing only."
Write-Host "Safety: research backtest only; no Dry-run, no live trading, no real API key."
Write-Host "Default mode is preview only. Add -Run to execute Docker."

if ($Run) {
  & docker @dockerArgs
} else {
  Write-Host "Preview only. No backtest was executed."
}
