param(
  [string]$PythonPath = "python",
  [string]$ManualReport = "reports/v13_7_13_manual_factor_library_report.json",
  [string]$EvaluationReport = "reports/v13_7_13_factor_evaluation_report.json",
  [string]$RegistryPath = "data/evolution_registry.sqlite",
  [string]$OutputJson = "reports/factor_research_kernel_baseline_report.json",
  [string]$OutputMarkdown = "reports/factor_research_kernel_baseline_summary.md"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Write-Host "AlphaPilot V13.12.0 factor research kernel baseline"
Write-Host "ManualReport: $ManualReport"
Write-Host "EvaluationReport: $EvaluationReport"
Write-Host "Legacy factor values are not loaded or modified"
Write-Host "Candidate promotion, Demo release, and order creation: disabled"

Push-Location $repoRoot
try {
  & $PythonPath -m alphapilot.reports.generate_factor_research_kernel_baseline `
    --manual-report $ManualReport `
    --evaluation-report $EvaluationReport `
    --registry-path $RegistryPath `
    --output-json $OutputJson `
    --output-markdown $OutputMarkdown
  $exitCode = $LASTEXITCODE
}
finally {
  Pop-Location
}

if ($exitCode -ne 0) {
  throw "Factor research kernel baseline failed with exit code $exitCode"
}
