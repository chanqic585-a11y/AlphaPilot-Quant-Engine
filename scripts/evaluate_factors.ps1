param(
  [string]$Timerange = "20260101-",
  [string]$Timeframe = "1h",
  [string]$Pairs = "",
  [string]$Horizons = "4,8,12,24",
  [double]$TpPct = 0.05,
  [double]$SlPct = 0.025,
  [int]$Quantiles = 5,
  [string]$FactorPanel = "",
  [string]$OutputReport = "reports/v13_4_22_factor_evaluation_report.json",
  [string]$OutputSummary = "reports/v13_4_22_factor_evaluation_summary.md",
  [string]$OutputCandidates = "reports/v13_4_22_factor_candidates.json"
)

$ErrorActionPreference = "Stop"

$arguments = @(
  "-m", "alphapilot.factors.evaluate_factors",
  "--timerange", $Timerange,
  "--timeframe", $Timeframe,
  "--horizons", $Horizons,
  "--tp-pct", $TpPct,
  "--sl-pct", $SlPct,
  "--quantiles", $Quantiles,
  "--output-report", $OutputReport,
  "--output-summary", $OutputSummary,
  "--output-candidates", $OutputCandidates
)

if ($Pairs.Trim().Length -gt 0) {
  $arguments += @("--pairs", $Pairs)
}

if ($FactorPanel.Trim().Length -gt 0) {
  $arguments += @("--factor-panel", $FactorPanel)
}

Write-Host "Evaluating AlphaPilot V13.4.22 factors from local research data..."
Write-Host "Timerange: $Timerange"
Write-Host "Timeframe: $Timeframe"
Write-Host "Horizons: $Horizons"
Write-Host "TP / SL: $TpPct / $SlPct"
Write-Host "Quantiles: $Quantiles"
Write-Host "No strategy backtest, Dry-run, API key, account read, order, or auto trading is performed."

& python @arguments
