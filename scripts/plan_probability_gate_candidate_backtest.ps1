param(
  [switch]$ShowJson
)

$ErrorActionPreference = "Stop"

$reportPath = "reports/v13_4_20_probability_gate_candidate_plan.json"
$summaryPath = "reports/v13_4_20_probability_gate_candidate_summary.md"

Write-Host "AlphaPilot V13.4.20 probability gate candidate backtest plan"
Write-Host "This script only prints the V13.4.21 plan. It does not run Freqtrade or any backtest."

if (-not (Test-Path $reportPath)) {
  Write-Host "Plan report not found: $reportPath"
  Write-Host "Generate it with: python -m alphapilot.reports.generate_probability_gate_candidate_plan"
  exit 0
}

if ($ShowJson) {
  Get-Content -LiteralPath $reportPath -Raw
  exit 0
}

if (Test-Path $summaryPath) {
  Get-Content -LiteralPath $summaryPath
} else {
  Write-Host "Summary not found: $summaryPath"
  Write-Host "Report is available at: $reportPath"
}
