param(
  [string]$Timerange = "20240101-",
  [string]$Pairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT",
  [switch]$UseMainstream,
  [switch]$UseTop10,
  [string]$Strategies = "all",
  [switch]$Run
)

$ErrorActionPreference = "Stop"

$allStrategies = @(
  "AlphaPilotBatchA_EMATrendLong4H",
  "AlphaPilotBatchB_EMATrendShort4H",
  "AlphaPilotBatchC_BreakoutRetestLong4H",
  "AlphaPilotBatchD_BreakdownRetestShort4H",
  "AlphaPilotBatchE_BollingerReversionLong4H",
  "AlphaPilotBatchF_BollingerReversionShort4H",
  "AlphaPilotBatchG_RelativeStrengthLong4H",
  "AlphaPilotBatchH_VolatilityCompressionBreakout4H"
)

function Split-CsvArg {
  param([string]$Value)
  return $Value.Split(",") |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_.Length -gt 0 }
}

function Write-Utf8NoBom {
  param(
    [string]$Path,
    [string]$Value
  )
  $parent = Split-Path -Parent $Path
  if ($parent -and -not (Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent | Out-Null
  }
  $encoding = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText((Join-Path (Get-Location) $Path), $Value, $encoding)
}

if ($UseMainstream) {
  $Pairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT"
}
if ($UseTop10) {
  $Pairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT,DOGE/USDT:USDT,XRP/USDT:USDT,ADA/USDT:USDT,AVAX/USDT:USDT,LINK/USDT:USDT,SUI/USDT:USDT,APT/USDT:USDT"
}

$pairList = @(Split-CsvArg $Pairs)
if ($Strategies -eq "all") {
  $strategyList = $allStrategies
} else {
  $strategyList = @(Split-CsvArg $Strategies)
}

$manifestPath = "reports/v13_4_35_multi_strategy_batch_manifest.json"
$results = @()
$failedStrategies = @()

Write-Host "AlphaPilot V13.4.35 multi-strategy research batch"
Write-Host "Pairs: $($pairList -join ', ')"
Write-Host "Timerange: $Timerange"
Write-Host "Strategies: $($strategyList -join ', ')"
Write-Host "Timeframe: 4h"
Write-Host "Fee model: 0.05% one-way via --fee 0.0005"
Write-Host "Slippage model: post-processing only; not applied by Freqtrade."
Write-Host "Research backtest only. No Dry-run, no live trading, no private API, no orders."
Write-Host "Default mode is preview only. Add -Run to execute Docker."

foreach ($strategy in $strategyList) {
  $resultZip = "user_data/backtest_results/v13_4_35_$strategy.zip"
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
    "4h",
    "--fee",
    "0.0005",
    "--export",
    "trades",
    "--pairs"
  ) + $pairList

  Write-Host ""
  Write-Host "Strategy: $strategy"
  Write-Host ("docker " + ($dockerArgs -join " "))

  $entry = [ordered]@{
    strategyClass = $strategy
    status = "preview"
    exitCode = $null
    timerange = $Timerange
    timeframe = "4h"
    pairs = $pairList
    resultZipPath = $null
    error = $null
    startedAt = (Get-Date).ToUniversalTime().ToString("o")
    completedAt = $null
  }

  if ($Run) {
    try {
      & docker @dockerArgs
      $exitCode = $LASTEXITCODE
      $entry.exitCode = $exitCode
      if ($exitCode -eq 0) {
        $lastResultPath = "user_data/backtest_results/.last_result.json"
        if (Test-Path $lastResultPath) {
          $lastResult = Get-Content $lastResultPath -Raw | ConvertFrom-Json
          if ($lastResult.latest_backtest) {
            $latestPath = Join-Path "user_data/backtest_results" $lastResult.latest_backtest
            if (Test-Path $latestPath) {
              Copy-Item -LiteralPath $latestPath -Destination $resultZip -Force
              $entry.status = "success"
              $entry.resultZipPath = $resultZip
              Write-Host "Copied latest Freqtrade result to $resultZip"
            } else {
              $entry.status = "result_missing"
              $entry.error = "latest_backtest path missing: $latestPath"
              $failedStrategies += $strategy
            }
          } else {
            $entry.status = "result_missing"
            $entry.error = ".last_result.json did not include latest_backtest"
            $failedStrategies += $strategy
          }
        } else {
          $entry.status = "result_missing"
          $entry.error = ".last_result.json not found"
          $failedStrategies += $strategy
        }
      } else {
        $entry.status = "failed"
        $entry.error = "docker exited with code $exitCode"
        $failedStrategies += $strategy
      }
    } catch {
      $entry.status = "failed"
      $entry.exitCode = $LASTEXITCODE
      $entry.error = $_.Exception.Message
      $failedStrategies += $strategy
    }
  }
  $entry.completedAt = (Get-Date).ToUniversalTime().ToString("o")
  $results += [pscustomobject]$entry
}

$manifest = [ordered]@{
  reportId = "v13_4_35_multi_strategy_batch_manifest"
  version = "V13.4.35"
  runMode = $(if ($Run) { "executed" } else { "preview" })
  timerange = $Timerange
  timeframe = "4h"
  pairs = $pairList
  strategies = $strategyList
  expandedTop10Executed = [bool]$UseTop10
  results = $results
  failedStrategies = @($failedStrategies | Select-Object -Unique)
  safetyBoundary = [ordered]@{
    dryRunApproved = $false
    liveTradingApproved = $false
    tradeApiUsed = $false
    withdrawApiUsed = $false
    apiKeyStored = $false
    accountRead = $false
    positionRead = $false
    orderCreated = $false
    autoTradingUsed = $false
  }
  generatedAt = (Get-Date).ToUniversalTime().ToString("o")
}

$json = $manifest | ConvertTo-Json -Depth 12
Write-Utf8NoBom -Path $manifestPath -Value ($json + "`n")
Write-Host ""
Write-Host "Wrote $manifestPath"
