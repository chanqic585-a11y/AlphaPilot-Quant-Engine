param(
  [ValidateSet("FreezePrefilter", "Prefilter", "FreezeFormal", "Formal")]
  [string]$Stage,
  [string]$DataRoot = "D:\Codex-Workspace\回测数据",
  [string]$PythonPath = "",
  [switch]$Run
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not $Run) {
  throw "This command is explicit-only. Add -Run after reviewing the stage."
}
if (-not (Test-Path -LiteralPath $DataRoot -PathType Container)) {
  throw "Data root does not exist: $DataRoot"
}
if (-not $PythonPath) {
  $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
  $PythonPath = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
}

$stageMap = @{
  FreezePrefilter = "freeze-prefilter"
  Prefilter = "prefilter"
  FreezeFormal = "freeze-formal"
  Formal = "formal"
}

Write-Host "AlphaPilot V13.27.1.13 bounded strategy campaign"
Write-Host "Stage: $Stage"
Write-Host "Data root is read-only: $DataRoot"
Write-Host "No download, cleanup, Demo Release, ARM, account access, or order action is performed."

Push-Location $repoRoot
try {
  & $PythonPath -m alphapilot.minimal_research_campaign.campaign_runner `
    --stage $stageMap[$Stage] `
    --repo-root $repoRoot `
    --data-root $DataRoot
  if ($LASTEXITCODE -ne 0) {
    throw "Minimal strategy campaign failed with exit code $LASTEXITCODE."
  }
} finally {
  Pop-Location
}
