param(
  [string]$Pairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT",
  [string]$Timeframes = "15m,1h,4h",
  [string]$Timerange = "20240101-",
  [switch]$Run
)

function Split-CsvArg {
  param([string]$Value)
  return $Value.Split(",") |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_.Length -gt 0 }
}

$pairList = @(Split-CsvArg $Pairs)
$timeframeList = @(Split-CsvArg $Timeframes)

$dockerArgs = @(
  "compose",
  "run",
  "--rm",
  "freqtrade",
  "download-data",
  "--config",
  "user_data/config/config.backtest.json",
  "--exchange",
  "okx",
  "--trading-mode",
  "futures",
  "--timerange",
  $Timerange,
  "--pairs"
) + $pairList + @("--timeframes") + $timeframeList

$commandPreview = "docker " + ($dockerArgs -join " ")

Write-Host "AlphaPilot V13.3 public historical data download command:"
Write-Host $commandPreview
Write-Host "Pairs: $($pairList -join ', ')"
Write-Host "Timeframes: $($timeframeList -join ', ')"
Write-Host "Timerange: $Timerange"
Write-Host "Default mode is preview only. Add -Run to execute Docker."

if ($Run) {
  & docker @dockerArgs
} else {
  Write-Host "Dry preview only. No data was downloaded."
}
