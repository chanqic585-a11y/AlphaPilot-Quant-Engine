param(
  [string]$PythonPath = ".venv\Scripts\python.exe",
  [string[]]$Instruments = @("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP"),
  [ValidateSet("5m", "15m", "1h", "4h", "1d")]
  [string[]]$Timeframes = @("15m", "1h", "4h", "1d")
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$resolvedPython = if ([System.IO.Path]::IsPathRooted($PythonPath)) { $PythonPath } else { Join-Path $repoRoot $PythonPath }
if (-not (Test-Path -LiteralPath $resolvedPython)) {
  throw "Python runtime not found: $resolvedPython"
}

$arguments = @(
  "-m", "alphapilot.reports.generate_v13_16_composite_snapshot_report",
  "--market-root", "data/market",
  "--registry-path", "data/evolution_registry.sqlite",
  "--instruments", ($Instruments -join ","),
  "--timeframes", ($Timeframes -join ","),
  "--market-type", "swap",
  "--output-json", "reports/v13_16_composite_data_snapshot_report.json",
  "--output-markdown", "reports/v13_16_composite_data_snapshot_summary.md"
)

Push-Location $repoRoot
try {
  & $resolvedPython @arguments
  $exitCode = $LASTEXITCODE
}
finally {
  Pop-Location
}
if ($exitCode -ne 0) {
  throw "V13.16 composite snapshot failed with exit code $exitCode"
}
