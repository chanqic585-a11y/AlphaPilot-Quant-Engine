param(
  [string]$Pairs = "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT",
  [string]$Timeframes = "4h,1d",
  [string]$Timerange = "20240101-",
  [switch]$RunDownload,
  [switch]$Prepend
)

$ErrorActionPreference = "Stop"

Write-Host "AlphaPilot V13.4.32 low-frequency baseline builder"
Write-Host "Pairs: $Pairs"
Write-Host "Timeframes: $Timeframes"
Write-Host "Timerange: $Timerange"
Write-Host "Report-only mode: no strategy backtest, no Dry-run, no private exchange API, no orders."

if ($RunDownload) {
  $downloadArgs = @(
    "-ExecutionPolicy", "Bypass",
    "-File", "scripts\download_data.ps1",
    "-Pairs", $Pairs,
    "-Timeframes", $Timeframes,
    "-Timerange", $Timerange,
    "-Run"
  )
  if ($Prepend) {
    $downloadArgs += "-Prepend"
  }
  powershell @downloadArgs
}

python -m alphapilot.reports.generate_low_frequency_baseline_report `
  --timerange $Timerange `
  --pairs $Pairs `
  --timeframes $Timeframes

Write-Host "Generated:"
Write-Host "reports/v13_4_32_low_frequency_data_report.json"
Write-Host "reports/v13_4_32_low_frequency_baseline_report.json"
Write-Host "reports/v13_4_32_low_frequency_baseline_summary.md"
