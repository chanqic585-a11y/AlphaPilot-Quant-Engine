param(
  [string]$Timerange = "20260101-",
  [string]$Pairs = "",
  [string]$Strategies = "BenchmarkEMATrend,BenchmarkRSIMeanReversion,BenchmarkMACDVolume,BenchmarkBollingerRebound,BenchmarkTD9Exhaustion",
  [switch]$UseTop10,
  [switch]$UseTop30,
  [switch]$Run
)

$ErrorActionPreference = "Stop"

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

function Get-Top10Pairs {
  return @(Get-Top30Pairs | Select-Object -First 10)
}

function Get-DockerCommand {
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if ($docker) {
    return $docker.Source
  }
  $candidate = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
  if (Test-Path -LiteralPath $candidate) {
    return $candidate
  }
  return "docker"
}

function Get-LatestBacktestName {
  $lastResultPath = "user_data/backtest_results/.last_result.json"
  if (-not (Test-Path -LiteralPath $lastResultPath)) {
    return $null
  }
  $lastResult = Get-Content -LiteralPath $lastResultPath -Raw -Encoding UTF8 | ConvertFrom-Json
  return $lastResult.latest_backtest
}

$pairList = if ($Pairs.Trim().Length -gt 0) {
  @(Split-CsvArg $Pairs)
} elseif ($UseTop30) {
  @(Get-Top30Pairs)
} else {
  @(Get-Top10Pairs)
}

$pairsMode = if ($Pairs.Trim().Length -gt 0) {
  "custom"
} elseif ($UseTop30) {
  "top30"
} else {
  "top10"
}

$strategyList = @(Split-CsvArg $Strategies)
$dockerCommand = Get-DockerCommand
$manifestPath = "reports/v13_4_23_benchmark_manifest.json"
$manifest = [ordered]@{
  reportId = "v13_4_23_benchmark_manifest"
  timerange = $Timerange
  timeframe = "1h"
  pairsMode = $pairsMode
  pairs = $pairList
  strategiesRequested = $strategyList
  strategies = @()
  generatedAt = (Get-Date).ToUniversalTime().ToString("o")
  safety = "Research-only Freqtrade backtest. No Dry-run, no live trading, no API keys, no Trade API, no Withdraw API."
}

foreach ($strategy in $strategyList) {
  $safeName = $strategy -replace "[^A-Za-z0-9_]", "_"
  $exportFile = "user_data/backtest_results/v13_4_23_$safeName.json"
  $stableZip = "user_data/backtest_results/v13_4_23_$safeName.zip"
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
    "1h",
    "--fee",
    "0.0005",
    "--export",
    "trades",
    "--export-filename",
    $exportFile,
    "--pairs"
  ) + $pairList

  $commandPreview = $dockerCommand + " " + ($dockerArgs -join " ")
  Write-Host ""
  Write-Host "AlphaPilot V13.4.23 benchmark command:"
  Write-Host $commandPreview
  Write-Host "Strategy: $strategy"
  Write-Host "Timerange: $Timerange"
  Write-Host "Pairs mode: $pairsMode"
  Write-Host "Pairs: $($pairList -join ', ')"
  Write-Host "Default mode is preview only. Add -Run to execute Docker."

  $entry = [ordered]@{
    strategy = $strategy
    command = $commandPreview
    requestedExportFile = $exportFile
    stableResult = $stableZip
    succeeded = $false
    exitCode = $null
    error = $null
    latestBacktest = $null
  }

  if ($Run) {
    & $dockerCommand @dockerArgs
    $exitCode = $LASTEXITCODE
    $entry.exitCode = $exitCode
    if ($exitCode -eq 0) {
      $latestBacktest = Get-LatestBacktestName
      $entry.latestBacktest = $latestBacktest
      if ($latestBacktest) {
        $latestPath = Join-Path "user_data/backtest_results" $latestBacktest
        if (Test-Path -LiteralPath $latestPath) {
          Copy-Item -LiteralPath $latestPath -Destination $stableZip -Force
          $entry.succeeded = $true
        } else {
          $entry.error = "latest_backtest file not found: $latestPath"
        }
      } else {
        $entry.error = "No latest_backtest value found after command."
      }
    } else {
      $entry.error = "Freqtrade benchmark failed with exit code $exitCode."
    }
  }

  $manifest.strategies += $entry
}

$manifestJson = $manifest | ConvertTo-Json -Depth 8
[System.IO.Directory]::CreateDirectory((Split-Path -Parent $manifestPath)) | Out-Null
[System.IO.File]::WriteAllText((Resolve-Path ".").Path + "\" + $manifestPath, $manifestJson, [System.Text.UTF8Encoding]::new($false))

Write-Host ""
Write-Host "Benchmark manifest written: $manifestPath"
if (-not $Run) {
  Write-Host "Preview complete. No benchmark backtest was executed."
}
