param(
  [string]$DataRoot = "D:\Codex-Workspace\回测数据",
  [int]$TargetSize = 20,
  [double]$MinimumHistoryMonths = 24,
  [string]$PythonPath = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not $PythonPath) {
  $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
  if (Test-Path -LiteralPath $venvPython) {
    $PythonPath = $venvPython
  } else {
    $PythonPath = "python"
  }
}

if (-not (Test-Path -LiteralPath $DataRoot -PathType Container)) {
  throw "Data root does not exist: $DataRoot"
}

$gitCommit = (& git -C $repoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or -not $gitCommit) {
  throw "Unable to resolve the current Quant commit."
}

Write-Host "AlphaPilot V13.27.1.13 minimal formal data layer"
Write-Host "Data root (read-only): $DataRoot"
Write-Host "Core target size: $TargetSize"
Write-Host "Minimum history months: $MinimumHistoryMonths"
Write-Host "No download, no market-data copy, and no cleanup is performed."

Push-Location $repoRoot
try {
  & $PythonPath -m alphapilot.minimal_research_campaign.data_layer_builder `
    --data-root $DataRoot `
    --repo-root $repoRoot `
    --target-size $TargetSize `
    --minimum-history-months $MinimumHistoryMonths `
    --git-commit $gitCommit
  if ($LASTEXITCODE -ne 0) {
    throw "Minimal data layer build failed with exit code $LASTEXITCODE."
  }
} finally {
  Pop-Location
}

Write-Host "Generated manifest-only evidence under reports/minimal_data_layer and research/data_snapshots."
