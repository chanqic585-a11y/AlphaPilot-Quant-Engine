param(
  [string]$Timerange = "20260101-",
  [string]$Timeframe = "1h",
  [string]$UniversePath = "reports/v13_4_13_dynamic_universe_snapshots.json",
  [switch]$Run
)

$ErrorActionPreference = "Stop"

$dockerBin = "C:\Program Files\Docker\Docker\resources\bin"
if ((Test-Path $dockerBin) -and ($env:Path -notlike "*$dockerBin*")) {
  $env:Path = "$dockerBin;$env:Path"
}

function Get-DynamicUniversePairs {
  param([string]$Path)

  if (-not (Test-Path $Path)) {
    throw "Dynamic universe snapshot file not found: $Path"
  }

  $snapshots = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
  $pairs = New-Object System.Collections.Generic.HashSet[string]

  foreach ($snapshot in $snapshots) {
    foreach ($pair in $snapshot.selectedPairs) {
      [void]$pairs.Add([string]$pair)
    }
  }

  $result = @()
  foreach ($item in $pairs) {
    $result += $item
  }
  $result = @($result | Sort-Object)
  if ($result.Count -eq 0) {
    throw "Dynamic universe contains no selected pairs."
  }

  return $result
}

$pairs = @(Get-DynamicUniversePairs -Path $UniversePath)
$pairsCsv = $pairs -join ","
$scriptPath = Join-Path $PSScriptRoot "run_backtest.ps1"
$argsList = @(
  "-Strategy",
  "AlphaPilotDynamicRegimeV01",
  "-Timeframe",
  $Timeframe,
  "-Timerange",
  $Timerange,
  "-Pairs",
  $pairsCsv
)

if ($Run) {
  $argsList += "-Run"
}

Write-Host "AlphaPilot V13.4.17 Dynamic Regime expanded validation wrapper"
Write-Host "Universe source: $UniversePath"
Write-Host "Dynamic universe pair count: $($pairs.Count)"
Write-Host "Pairs: $pairsCsv"
Write-Host "Timerange: $Timerange"
Write-Host "Timeframe: $Timeframe"
Write-Host "Strategy: AlphaPilotDynamicRegimeV01"
Write-Host "This wrapper runs a local Freqtrade backtest only. It does not enter Dry-run or live trading."

& powershell -ExecutionPolicy Bypass -File $scriptPath @argsList
