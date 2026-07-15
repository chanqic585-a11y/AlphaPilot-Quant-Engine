param(
  [string]$Preregistration,
  [switch]$Run
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = 'D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe'
if (-not $Preregistration) {
  $files = @(Get-ChildItem -LiteralPath (Join-Path $repo 'research\preregistrations') -Filter 'phase3c_campaign_*.json')
  if ($files.Count -ne 1) { throw "Expected exactly one Phase 3C preregistration, found $($files.Count)." }
  $Preregistration = $files[0].FullName
}

if (-not $Run) {
  Write-Host "Plan only: run the offline bounded campaign from $Preregistration."
  Write-Host 'Re-run with -Run to execute and write results.'
  exit 0
}

& $python -m alphapilot.research_screening.campaign_runner --repo $repo --preregistration $Preregistration
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
