$ErrorActionPreference = "Stop"

$python = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (-not (Test-Path $python)) {
  $python = "python"
}

& $python -m alphapilot.reports.generate_demo_promotion_readiness_report
exit $LASTEXITCODE
