param(
  [switch]$Run
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = 'D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe'
$commit = (git -C $repo rev-parse HEAD).Trim()

if (-not $Run) {
  Write-Host "Plan only: preregister the bounded Phase 3C campaign at implementation commit $commit."
  Write-Host 'Re-run with -Run to create the immutable preregistration.'
  exit 0
}

& $python -m alphapilot.research_screening.campaign_preregistration --repo $repo --code-commit $commit
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
