param(
  [string]$Timerange = "20260101-",
  [string]$Timeframe = "1h",
  [string]$Pairs = "",
  [switch]$UseDynamicUniverse,
  [string]$UniverseSnapshots = "reports/v13_4_13_dynamic_universe_snapshots.json",
  [string]$OutputPanelSample = "reports/v13_4_21_factor_panel_sample.json",
  [string]$OutputReport = "reports/v13_4_21_factor_panel_report.json",
  [string]$OutputSummary = "reports/v13_4_21_factor_panel_summary.md",
  [string]$OutputManualFactorReport = "reports/v13_4_21_manual_factor_library_report.json"
)

$ErrorActionPreference = "Stop"

$arguments = @(
  "-m", "alphapilot.factors.build_factor_data_panel",
  "--timerange", $Timerange,
  "--timeframe", $Timeframe,
  "--output-panel-sample", $OutputPanelSample,
  "--output-report", $OutputReport,
  "--output-summary", $OutputSummary,
  "--output-manual-factor-report", $OutputManualFactorReport,
  "--universe-snapshots", $UniverseSnapshots
)

if ($Pairs.Trim().Length -gt 0) {
  $arguments += @("--pairs", $Pairs)
}

if ($UseDynamicUniverse) {
  $arguments += "--use-dynamic-universe"
}

Write-Host "Building AlphaPilot V13.4.21 FactorDataPanel from local public OHLCV..."
Write-Host "Timerange: $Timerange"
Write-Host "Timeframe: $Timeframe"
if ($Pairs.Trim().Length -gt 0) {
  Write-Host "Pairs: $Pairs"
} else {
  Write-Host "Pairs: auto-discovered local pairs"
}
Write-Host "Dynamic universe: $($UseDynamicUniverse.IsPresent)"

& python @arguments
