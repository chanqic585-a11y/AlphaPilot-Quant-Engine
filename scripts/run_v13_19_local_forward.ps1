param(
  [switch]$Loop,
  [int]$PollSeconds = 60,
  [string]$AccountId = "default_forward_account"
)

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
if ($PollSeconds -lt 30) {
  throw "PollSeconds must be at least 30. Forward evidence follows real completed candles."
}

Push-Location -LiteralPath $repoRoot
try {
  do {
    $codeCommit = (& $git rev-parse HEAD).Trim()
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python -m alphapilot.reports.generate_v13_19_local_forward_report `
      --code-commit $codeCommit `
      --account-id $AccountId `
      --observe
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $contract = Get-Content -LiteralPath "reports\v13_19_local_forward_contract.json" -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $Loop -or $contract.status -eq "blocked_no_eligible_forward_release") {
      break
    }
    Start-Sleep -Seconds $PollSeconds
  } while ($true)
} finally {
  Pop-Location
}
