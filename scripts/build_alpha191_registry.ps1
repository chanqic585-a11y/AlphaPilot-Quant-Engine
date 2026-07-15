param([switch]$Run)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Candidates = @(
    $env:ALPHAPILOT_PYTHON,
    (Join-Path $RepoRoot ".venv\Scripts\python.exe"),
    (Join-Path $RepoRoot "..\..\.venv\Scripts\python.exe")
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

Write-Host "Alpha191 registry plan: register all 191 metadata records and keep unresolved formulas non-executable."
if (-not $Run) {
    Write-Host "Dry run only. Add -Run to write reports/factor_lab."
    exit 0
}
if (-not $Candidates) { throw "No AlphaPilot Python runtime found." }
$Python = @($Candidates)[0]
Push-Location $RepoRoot
try {
    & $Python -m alphapilot.factor_lab.alpha191.build_registry
    if ($LASTEXITCODE -ne 0) { throw "Alpha191 registry build failed." }
} finally {
    Pop-Location
}
