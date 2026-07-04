param(
  [string]$UniverseSnapshots = "reports/v13_4_13_dynamic_universe_snapshots.json",
  [string]$Timerange = "20260101-",
  [string]$Timeframe = "1h",
  [double]$TpPct = 0.05,
  [double]$SlPct = 0.025,
  [string]$Windows = "8,12,24",
  [string]$DataPath = "user_data/data/okx/futures",
  [string]$OutputReport = "reports/v13_4_14_probability_dataset_report.json",
  [string]$OutputScoreTable = "reports/v13_4_14_probability_score_table.json",
  [string]$OutputSummary = "reports/v13_4_14_probability_dataset_summary.md",
  [string]$OutputSampleDataset = "reports/v13_4_14_probability_sample_dataset.json"
)

$ErrorActionPreference = "Stop"

function Get-PythonCommand {
  $bundled = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
  if (Test-Path -LiteralPath $bundled) {
    return $bundled
  }
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    return $python.Source
  }
  return "python"
}

$pythonCommand = Get-PythonCommand

$argsList = @(
  "-m",
  "alphapilot.probability.build_probability_dataset",
  "--universe-snapshots",
  $UniverseSnapshots,
  "--timerange",
  $Timerange,
  "--timeframe",
  $Timeframe,
  "--tp-pct",
  "$TpPct",
  "--sl-pct",
  "$SlPct",
  "--windows",
  $Windows,
  "--data-path",
  $DataPath,
  "--output-report",
  $OutputReport,
  "--output-score-table",
  $OutputScoreTable,
  "--output-summary",
  $OutputSummary,
  "--output-sample-dataset",
  $OutputSampleDataset
)

Write-Host ("Running: {0} {1}" -f $pythonCommand, ($argsList -join " "))
& $pythonCommand @argsList
