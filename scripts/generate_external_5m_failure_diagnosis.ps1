param(
  [string]$Ranking = "reports/external_5m_strategy_ranking.json",
  [string]$OutputJson = "reports/external_5m_failure_diagnosis.json",
  [string]$OutputSummary = "reports/external_5m_failure_diagnosis_summary.md",
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

Write-Host "AlphaPilot external 5m failure diagnosis"
Write-Host "Ranking: $Ranking"
Write-Host "OutputJson: $OutputJson"
Write-Host "OutputSummary: $OutputSummary"
Write-Host "PythonExe: $PythonExe"
Write-Host "Research report only. No Dry-run, no live trading, no private API, no orders."

& $PythonExe -m alphapilot.reports.generate_external_5m_failure_diagnosis `
  --ranking $Ranking `
  --output-json $OutputJson `
  --output-summary $OutputSummary
