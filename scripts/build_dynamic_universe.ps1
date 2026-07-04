param(
  [string]$Timerange = "20260101-",
  [ValidateSet("daily", "3d")]
  [string]$RefreshFrequency = "daily",
  [int]$MaxPairs = 10,
  [ValidateSet("top30")]
  [string]$CandidateMode = "top30",
  [string]$Output = "reports/v13_4_13_dynamic_universe_snapshots.json",
  [string]$SampleOutput = "reports/v13_4_13_dynamic_universe_sample_snapshots.json",
  [string]$BuildReport = "reports/v13_4_13_dynamic_universe_build_report.json",
  [string]$Summary = "reports/v13_4_13_dynamic_universe_summary.md",
  [string]$DataPath = "user_data/data/okx/futures"
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
  "alphapilot.universe.build_historical_dynamic_universe",
  "--timerange",
  $Timerange,
  "--refresh-frequency",
  $RefreshFrequency,
  "--max-pairs",
  "$MaxPairs",
  "--candidate-mode",
  $CandidateMode,
  "--output",
  $Output,
  "--sample-output",
  $SampleOutput,
  "--build-report",
  $BuildReport,
  "--summary",
  $Summary,
  "--data-path",
  $DataPath
)

Write-Host ("Running: {0} {1}" -f $pythonCommand, ($argsList -join " "))
& $pythonCommand @argsList
