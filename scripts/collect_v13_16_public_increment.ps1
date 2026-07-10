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

$instrumentCsv = $Instruments -join ","
$timeframeCsv = $Timeframes -join ","
$arguments = @(
  "-m", "alphapilot.reports.generate_v13_16_public_increment_report",
  "--canonical-root", "data/market/canonical",
  "--instruments", $instrumentCsv,
  "--timeframes", $timeframeCsv,
  "--output-json", "reports/v13_16_public_increment_report.json"
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
  throw "V13.16 public increment collection failed with exit code $exitCode"
}
