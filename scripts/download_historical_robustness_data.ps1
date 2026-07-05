param(
  [string]$Exchanges = "okx,binance,bybit",
  [string]$Pairs = "",
  [string]$Timeframes = "4h,1d",
  [string]$Timerange = "20200101-",
  [int]$BatchSize = 20,
  [switch]$UseTop100,
  [switch]$Prepend,
  [switch]$Run
)

$ErrorActionPreference = "Stop"

$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$pythonExe = "python"
if (Test-Path $BundledPython) {
  $pythonExe = $BundledPython
}

function Split-CsvArg {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) {
    return @()
  }
  return $Value.Split(",") |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_.Length -gt 0 }
}

function Get-Top100Pairs {
  $raw = & $pythonExe -m alphapilot.universe.top100_usdt_swap_research
  if ($LASTEXITCODE -ne 0) {
    throw "Unable to load Top100 research pair list."
  }
  return @(Split-CsvArg $raw)
}

function Get-Batches {
  param(
    [string[]]$Items,
    [int]$Size
  )
  $batches = @()
  for ($index = 0; $index -lt $Items.Count; $index += $Size) {
    $end = [Math]::Min($index + $Size - 1, $Items.Count - 1)
    $batches += ,@($Items[$index..$end])
  }
  return $batches
}

$exchangeList = @(Split-CsvArg $Exchanges)
$pairList = if ($UseTop100) {
  @(Get-Top100Pairs)
} else {
  @(Split-CsvArg $Pairs)
}
if ($pairList.Count -eq 0) {
  $pairList = @("BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT")
}
$timeframeList = @(Split-CsvArg $Timeframes)
$pairBatches = @(Get-Batches -Items $pairList -Size $BatchSize)

Write-Host "AlphaPilot historical robustness public data expansion"
Write-Host "Exchanges: $($exchangeList -join ', ')"
Write-Host "Pairs: $($pairList.Count)"
Write-Host "Timeframes: $($timeframeList -join ', ')"
Write-Host "Timerange: $Timerange"
Write-Host "BatchSize: $BatchSize"
Write-Host "Prepend: $Prepend"
Write-Host "Run: $Run"
Write-Host "No API keys, no private endpoints, no account reads, no orders."

foreach ($exchange in $exchangeList) {
  $batchNumber = 0
  foreach ($batch in $pairBatches) {
    $batchNumber += 1
    $dockerArgs = @(
      "compose",
      "run",
      "--rm",
      "freqtrade",
      "download-data",
      "--config",
      "user_data/config/config.backtest.json",
      "--exchange",
      $exchange,
      "--trading-mode",
      "futures",
      "--timerange",
      $Timerange,
      "--pairs"
    ) + $batch + @("--timeframes") + $timeframeList

    if ($Prepend) {
      $dockerArgs += "--prepend"
    }

    $commandPreview = "docker " + ($dockerArgs -join " ")
    Write-Host ""
    Write-Host "[$exchange batch $batchNumber/$($pairBatches.Count)]"
    Write-Host $commandPreview

    if ($Run) {
      & docker @dockerArgs
      if ($LASTEXITCODE -ne 0) {
        Write-Warning "Download failed for $exchange batch $batchNumber. Continuing so other batches can finish."
      }
      Start-Sleep -Seconds 3
    }
  }
}

if (-not $Run) {
  Write-Host ""
  Write-Host "Preview only. Add -Run to download public historical data."
}
