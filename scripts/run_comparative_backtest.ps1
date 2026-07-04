param(
  [string]$Timerange = "20260401-",
  [string]$Pairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT",
  [string]$Strategies = "AlphaPilotVolumeReboundV01,AlphaPilotVolumeReboundV02ATrendStrict,AlphaPilotVolumeReboundV02BVolumeQuality,AlphaPilotVolumeReboundV02CExitCleanup,AlphaPilotVolumeReboundV02DEarlyFailureExit,AlphaPilotVolumeReboundV02EPairRiskWatchlist",
  [switch]$Run
)

function Split-CsvArg {
  param([string]$Value)
  return $Value.Split(",") |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_.Length -gt 0 }
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

$pairList = @(Split-CsvArg $Pairs)
$strategyList = @(Split-CsvArg $Strategies)
$dockerCommand = Get-DockerCommand
$manifestPath = "reports/v13_4_4_comparative_manifest.json"
$manifest = [ordered]@{
  reportId = "v13_4_4_comparative_manifest"
  timerange = $Timerange
  pairs = $pairList
  strategies = @()
  generatedAt = (Get-Date).ToUniversalTime().ToString("o")
  safety = "Backtesting only. No Dry-run, no live trading, no API keys, no Trade API, no Withdraw API."
}

foreach ($strategy in $strategyList) {
  $safeName = $strategy -replace "[^A-Za-z0-9_]", "_"
  $exportFile = "user_data/backtest_results/v13_4_4_$safeName.json"
  $stableZip = "user_data/backtest_results/v13_4_4_$safeName.zip"
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
    "15m",
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
  Write-Host "AlphaPilot V13.4.4 comparative backtest command:"
  Write-Host $commandPreview
  Write-Host "Strategy: $strategy"
  Write-Host "Timerange: $Timerange"
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
      $entry.error = "Freqtrade backtest failed with exit code $exitCode."
    }
  }

  $manifest.strategies += $entry
}

$manifestJson = $manifest | ConvertTo-Json -Depth 8
[System.IO.Directory]::CreateDirectory((Split-Path -Parent $manifestPath)) | Out-Null
[System.IO.File]::WriteAllText((Resolve-Path ".").Path + "\" + $manifestPath, $manifestJson, [System.Text.UTF8Encoding]::new($false))

Write-Host ""
Write-Host "Comparative manifest written: $manifestPath"
if (-not $Run) {
  Write-Host "Preview complete. No backtest was executed."
}
