param(
  [string]$PythonPath = "python",
  [string]$ManualReport = "reports/v13_7_13_manual_factor_library_report.json",
  [string]$EvaluationReport = "reports/v13_7_13_factor_evaluation_report.json",
  [string]$RegistryPath = "data/evolution_registry.sqlite",
  [int]$ResearchBudget = 96,
  [int]$MaxCandidates = 48,
  [string]$OutputJson = "reports/evolution_cycle_report.json",
  [string]$OutputMarkdown = "reports/evolution_cycle_summary.md"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Write-Host "AlphaPilot V13.13.0 bounded evolution cycle"
Write-Host "ResearchBudget: $ResearchBudget"
Write-Host "MaxCandidates: $MaxCandidates"
Write-Host "Maximum lifecycle stage: shadow_research"
Write-Host "Demo/live promotion and order creation: disabled"

Push-Location $repoRoot
try {
  & $PythonPath -m alphapilot.reports.generate_evolution_cycle_report `
    --manual-report $ManualReport `
    --evaluation-report $EvaluationReport `
    --registry-path $RegistryPath `
    --research-budget $ResearchBudget `
    --max-candidates $MaxCandidates `
    --output-json $OutputJson `
    --output-markdown $OutputMarkdown
  $exitCode = $LASTEXITCODE
}
finally {
  Pop-Location
}

if ($exitCode -ne 0) {
  throw "Evolution cycle failed with exit code $exitCode"
}
