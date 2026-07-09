param(
  [string]$SourceDir = "",
  [string]$OutputDir = "user_data/data/local_contract_xlsx/okx/futures",
  [string]$Symbols = "BTC,GAS,ZRX,DOGE,CRO,ICX,APE,APT,GALA,LTC,MANA,NEAR,SAND,SOL,TRX,ADA,AXS",
  [string]$Timeframes = "1h,4h",
  [string]$ReportPath = "reports/contract_swap_xlsx_import_report.json",
  [switch]$Overwrite
)

$ErrorActionPreference = "Stop"

$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$PythonExe = if ($env:ALPHAPILOT_PYTHON) {
  $env:ALPHAPILOT_PYTHON
} elseif (Test-Path -LiteralPath $BundledPython) {
  $BundledPython
} else {
  "python"
}

$pythonArgs = @(
  "-m",
  "alphapilot.data_import.swap_xlsx_importer",
  "--output-dir",
  $OutputDir,
  "--symbols",
  $Symbols,
  "--timeframes",
  $Timeframes,
  "--report-path",
  $ReportPath
)

if ($SourceDir) {
  $pythonArgs += @("--source-dir", $SourceDir)
}
if ($Overwrite) {
  $pythonArgs += "--overwrite"
}

Write-Host "Importing local contract swap XLSX OHLCV data"
Write-Host "SourceDir: $SourceDir"
Write-Host "OutputDir: $OutputDir"
Write-Host "Symbols: $Symbols"
Write-Host "Timeframes: $Timeframes"
Write-Host "Research data import only. No API Key, no Trade API, no Withdraw API, no orders."
& $PythonExe @pythonArgs
