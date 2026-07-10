$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
  throw "AlphaPilot virtualenv Python not found: $python"
}
$bundledGit = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe"
$git = if (Test-Path -LiteralPath $bundledGit) {
  $bundledGit
} else {
  (Get-Command git -ErrorAction Stop).Source
}

Push-Location -LiteralPath $repoRoot
try {
  $codeCommit = (& $git rev-parse HEAD).Trim()
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  & $python -m alphapilot.reports.generate_v13_21_live_safety_candidate_report --code-commit $codeCommit
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
  Pop-Location
}
