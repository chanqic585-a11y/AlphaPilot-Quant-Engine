param(
  [string]$PythonPath = ".venv\Scripts\python.exe",
  [string]$RawRoot = "D:\Codex-Workspace\回测数据",
  [string]$Symbols = "BTC,ETH,SOL",
  [string]$Timeframes = "15m,1h,4h,1d",
  [ValidateSet("none", "selected", "all")]
  [string]$HashMode = "none",
  [switch]$Overwrite
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$resolvedPython = if ([System.IO.Path]::IsPathRooted($PythonPath)) { $PythonPath } else { Join-Path $repoRoot $PythonPath }
if (-not (Test-Path -LiteralPath $resolvedPython)) {
  throw "Python runtime not found: $resolvedPython"
}

$arguments = @(
  "-m", "alphapilot.reports.generate_v13_16_data_foundation_report",
  "--market-root", "data/market",
  "--registry-path", "data/evolution_registry.sqlite",
  "--symbols", $Symbols,
  "--timeframes", $Timeframes,
  "--market-type", "swap",
  "--exchange", "unknown",
  "--hash-mode", $HashMode,
  "--output-json", "reports/v13_16_data_foundation_report.json",
  "--output-markdown", "reports/v13_16_data_foundation_summary.md"
)
if ($RawRoot -ne "D:\Codex-Workspace\回测数据") {
  $arguments += @("--raw-root", $RawRoot)
}
if ($Overwrite) {
  $arguments += "--overwrite"
}

Push-Location $repoRoot
try {
  & $resolvedPython @arguments
  $exitCode = $LASTEXITCODE
}
finally {
  Pop-Location
}
if ($exitCode -ne 0) {
  throw "V13.16 data foundation failed with exit code $exitCode"
}
