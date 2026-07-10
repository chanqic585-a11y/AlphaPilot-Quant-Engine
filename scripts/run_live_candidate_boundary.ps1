$ErrorActionPreference = "Stop"

$python = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (-not (Test-Path $python)) {
  $python = "python"
}

& $python -m alphapilot.reports.generate_live_candidate_boundary_report
exit $LASTEXITCODE
