param(
  [switch]$Run,
  [string]$StartDate = "2024-01-01",
  [string]$EndDate = "2026-07-06",
  [string]$Symbols = ""
)

$ErrorActionPreference = "Stop"

$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$pythonExe = "python"
if (Test-Path $BundledPython) {
  $pythonExe = $BundledPython
}

$cmd = @(
  "-m",
  "alphapilot.reports.generate_v13_5_11_cross_market_data_smoke_report",
  "--start-date",
  $StartDate,
  "--end-date",
  $EndDate,
  "--output-report",
  "reports/v13_5_11_cross_market_public_data_smoke_report.json",
  "--output-summary",
  "reports/v13_5_11_cross_market_public_data_smoke_summary.md"
)

if ($Symbols.Trim().Length -gt 0) {
  $cmd += @("--symbols", $Symbols)
}

Write-Host "AlphaPilot V13.5.11 Cross-Market Public Data Smoke"
Write-Host "Research only. Public OHLCV samples are not trading signals or orders."
Write-Host "$pythonExe $($cmd -join ' ')"

if ($Run) {
  & $pythonExe @cmd
  if ($LASTEXITCODE -ne 0) {
    throw "V13.5.11 cross-market data smoke failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. Add -Run to fetch public data and generate reports."
}
