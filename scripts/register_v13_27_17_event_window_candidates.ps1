$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Registry = Join-Path $RepoRoot "data\evolution_registry.sqlite"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Project Python environment is missing: $Python"
}

Push-Location $RepoRoot
try {
    & $Python -m alphapilot.evolution.workflow.cli `
        --registry $Registry `
        bootstrap-v13-27-17-event-window
    if ($LASTEXITCODE -ne 0) {
        throw "V13.27.17 event-window registration failed with exit code $LASTEXITCODE"
    }
}
finally {
    Pop-Location
}
