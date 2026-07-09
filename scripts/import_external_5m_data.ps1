param(
  [string]$SourceDir = "E:\BaiduNetdiskDownload\5m",
  [string]$OutputDir = "user_data/data/local5m/okx/futures",
  [string]$Timeframes = "5m,15m,30m,1h,4h",
  [string]$Symbols = "",
  [int]$MaxPairs = 0,
  [switch]$Overwrite
)

$ErrorActionPreference = "Stop"

$pythonArgs = @(
  "-m",
  "alphapilot.data_import.external_5m_csv_importer",
  "--source-dir",
  $SourceDir,
  "--output-dir",
  $OutputDir,
  "--timeframes",
  $Timeframes
)

if ($Symbols) {
  $pythonArgs += @("--symbols", $Symbols)
}
if ($MaxPairs -gt 0) {
  $pythonArgs += @("--max-pairs", [string]$MaxPairs)
}
if ($Overwrite) {
  $pythonArgs += "--overwrite"
}

Write-Host "Importing external 5m OHLCV data"
Write-Host "SourceDir: $SourceDir"
Write-Host "OutputDir: $OutputDir"
Write-Host "Timeframes: $Timeframes"
Write-Host "Research data import only. No API Key, no Trade API, no Withdraw API, no orders."
python @pythonArgs
