param(
  [string]$Timerange = "20230101-",
  [string]$Pairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT,DOGE/USDT:USDT,XRP/USDT:USDT,ADA/USDT:USDT,AVAX/USDT:USDT,LINK/USDT:USDT,SUI/USDT:USDT,APT/USDT:USDT,OP/USDT:USDT,ARB/USDT:USDT,LTC/USDT:USDT,BCH/USDT:USDT,DOT/USDT:USDT,NEAR/USDT:USDT,PEPE/USDT:USDT,WIF/USDT:USDT,ORDI/USDT:USDT,INJ/USDT:USDT,FIL/USDT:USDT,ETC/USDT:USDT,TRX/USDT:USDT,UNI/USDT:USDT,AAVE/USDT:USDT,ATOM/USDT:USDT,SEI/USDT:USDT,TIA/USDT:USDT",
  [string]$DownloadTimeframes = "1h,4h",
  [string]$ReportTimeframes = "1h,4h",
  [switch]$RefreshPublicData,
  [switch]$Prepend,
  [switch]$Run
)

$ErrorActionPreference = "Stop"

Write-Host "AlphaPilot V13.5.5 event pool expansion"
Write-Host "Timerange: $Timerange"
Write-Host "Pairs: $Pairs"
Write-Host "Download timeframes: $DownloadTimeframes"
Write-Host "Report timeframes: $ReportTimeframes"
Write-Host "Refresh public data: $RefreshPublicData"
Write-Host "Prepend missing earlier local data: $Prepend"
Write-Host "Default mode is preview only. Add -Run to execute."

if (-not $Run) {
  Write-Host "Preview command:"
  Write-Host "powershell -ExecutionPolicy Bypass -File scripts/run_v13_5_5_event_pool_expansion.ps1 -RefreshPublicData -Prepend -Run"
  exit 0
}

if ($RefreshPublicData) {
  Write-Host "Checking Docker before public data refresh..."
  $previousErrorActionPreference = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  & docker info 1>$null 2>$null
  $dockerExitCode = $LASTEXITCODE
  $ErrorActionPreference = $previousErrorActionPreference
  if ($dockerExitCode -ne 0) {
    Write-Error "Docker is not ready. Start Docker Desktop and rerun this script."
    exit $dockerExitCode
  }

  $downloadArgs = @(
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    "scripts/download_data.ps1",
    "-Pairs",
    $Pairs,
    "-Timeframes",
    $DownloadTimeframes,
    "-Timerange",
    $Timerange,
    "-Run"
  )
  if ($Prepend) {
    $downloadArgs += "-Prepend"
  }
  & powershell @downloadArgs
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

& python -m alphapilot.reports.generate_v13_5_5_event_pool_expansion_report `
  --timeframes $ReportTimeframes `
  --output-report reports/v13_5_5_event_pool_expansion_report.json `
  --output-summary reports/v13_5_5_event_pool_expansion_summary.md `
  --output-candidates reports/v13_5_5_event_pool_candidates.json

if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
