param(
  [string]$Manifest = "reports/external_5m_all_strategy_backtest_manifest.json",
  [string]$OutputJson = "reports/external_5m_strategy_ranking.json",
  [string]$OutputSummary = "reports/external_5m_strategy_ranking_summary.md",
  [double]$SlippageRate = 0.0005,
  [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

if (-not $PythonExe) {
  $bundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  if (Test-Path -LiteralPath $bundledPython) {
    $PythonExe = $bundledPython
  } else {
    $PythonExe = "python"
  }
}

Write-Host "AlphaPilot external 5m strategy ranking"
Write-Host "Manifest: $Manifest"
Write-Host "OutputJson: $OutputJson"
Write-Host "OutputSummary: $OutputSummary"
Write-Host "SlippageRate: $SlippageRate"
Write-Host "PythonExe: $PythonExe"
Write-Host "Research report only. No Dry-run, no live trading, no private API, no orders."

& $PythonExe -m alphapilot.reports.generate_external_5m_strategy_ranking `
  --manifest $Manifest `
  --output-json $OutputJson `
  --output-summary $OutputSummary `
  --slippage-rate $SlippageRate
