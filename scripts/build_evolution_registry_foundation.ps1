param(
  [string]$PythonPath = "python",
  [string]$ReportsDir = "reports",
  [string]$RegistryPath = "data/evolution_registry.sqlite",
  [string]$OutputJson = "reports/evolution_registry_foundation_report.json",
  [string]$OutputMarkdown = "reports/evolution_registry_foundation_summary.md"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

Write-Host "AlphaPilot V13.11.0 evolution registry foundation"
Write-Host "ReportsDir: $ReportsDir"
Write-Host "RegistryPath: $RegistryPath"
Write-Host "Research-only import: enabled"
Write-Host "Strategy candidate, Demo release, and order creation: disabled"

Push-Location $repoRoot
try {
  & $PythonPath -m alphapilot.reports.generate_evolution_registry_foundation_report `
    --reports-dir $ReportsDir `
    --registry-path $RegistryPath `
    --output-json $OutputJson `
    --output-markdown $OutputMarkdown
  $exitCode = $LASTEXITCODE
}
finally {
  Pop-Location
}

if ($exitCode -ne 0) {
  throw "Evolution registry foundation failed with exit code $exitCode"
}
