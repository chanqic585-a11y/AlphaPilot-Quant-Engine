param(
  [switch]$Run,
  [string]$SourceText = "tmp/pdfs/alpha191_extracted_text.txt"
)

$ErrorActionPreference = "Stop"

$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$pythonExe = "python"
if (Test-Path $BundledPython) {
  $pythonExe = $BundledPython
}

$cmd = @(
  "-m",
  "alphapilot.reports.generate_v13_5_22_alpha191_factor_extraction_report",
  "--source-text",
  $SourceText,
  "--output-report",
  "reports/v13_5_22_alpha191_factor_extraction_report.json",
  "--output-summary",
  "reports/v13_5_22_alpha191_factor_extraction_summary.md",
  "--output-catalog",
  "reports/v13_5_22_alpha191_factor_candidate_catalog.json"
)

Write-Host "AlphaPilot V13.5.22 Alpha191 Factor Extraction"
Write-Host "Research metadata only. No formulas copied, no orders, no API keys, no auto trading."
Write-Host "$pythonExe $($cmd -join ' ')"

if ($Run) {
  & $pythonExe @cmd
  if ($LASTEXITCODE -ne 0) {
    throw "V13.5.22 Alpha191 factor extraction failed with exit code $LASTEXITCODE"
  }
} else {
  Write-Host "Preview only. Add -Run to generate reports."
}
