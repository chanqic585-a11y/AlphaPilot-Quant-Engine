param(
  [string]$Timerange = "20260101-",
  [string]$Timeframe = "1h",
  [switch]$UseTop30,
  [switch]$Run
)

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
  $lastResult = Get-Content -LiteralPath $lastResultPath -Raw | ConvertFrom-Json
  return $lastResult.latest_backtest
}

$strategy = "AlphaPilotTrendPullback1HV01"
$pairList = if ($UseTop30) { @(Get-Top30Pairs) } else { @("BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT") }
$dockerCommand = Get-DockerCommand
$manifestPath = "reports/v13_4_9_trend_pullback_expanded_manifest.json"
$stableZip = "user_data/backtest_results/v13_4_9_AlphaPilotTrendPullback1HV01.zip"
$exportFile = "user_data/backtest_results/v13_4_9_AlphaPilotTrendPullback1HV01.json"
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
  $Timeframe,
  "--fee",
  "0.0005",
  "--export",
  "trades",
  "--export-filename",
  $exportFile,
  "--pairs"
) + $pairList

$commandPreview = $dockerCommand + " " + ($dockerArgs -join " ")
Write-Host "AlphaPilot V13.4.9 Trend Pullback expanded validation command:"
Write-Host $commandPreview
Write-Host "Strategy: $strategy"
Write-Host "Timerange: $Timerange"
Write-Host "Timeframe: $Timeframe"
Write-Host "Pairs: $($pairList -join ', ')"
Write-Host "Fee model: 0.05% one-way via --fee 0.0005"
Write-Host "Slippage model: AlphaPilot post-processing only; not applied by Freqtrade command."
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
    $entry.error = "Freqtrade backtest failed with exit code $exitCode."
  }
}

$manifest = [ordered]@{
  reportId = "v13_4_9_trend_pullback_expanded_manifest"
  pairsMode = if ($UseTop30) { "fixed_top30" } else { "smoke" }
  timerange = $Timerange
  timeframe = $Timeframe
  pairs = $pairList
  strategiesRequested = @($strategy)
  strategies = @($entry)
  generatedAt = (Get-Date).ToUniversalTime().ToString("o")
  safety = "Backtesting only. No Dry-run, no live trading, no API keys, no Trade API, no Withdraw API."
}

$manifestJson = $manifest | ConvertTo-Json -Depth 8
[System.IO.Directory]::CreateDirectory((Split-Path -Parent $manifestPath)) | Out-Null
[System.IO.File]::WriteAllText((Resolve-Path ".").Path + "\" + $manifestPath, $manifestJson, [System.Text.UTF8Encoding]::new($false))

Write-Host "Trend Pullback expanded manifest written: $manifestPath"
if (-not $Run) {
  Write-Host "Preview complete. No backtest was executed."
}
