param(
    [string]$PythonExecutable = "",
    [string]$FixtureRoot = "",
    [string]$EvidenceRoot = "",
    [string]$ForbiddenLockedOosRoot = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not $PythonExecutable) {
    $worktreePython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    $parent = Split-Path -Parent $repoRoot
    $mainRepo = if ((Split-Path -Leaf $parent) -eq ".worktrees") {
        Split-Path -Parent $parent
    } else {
        $repoRoot
    }
    $mainPython = Join-Path $mainRepo ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $worktreePython) {
        $PythonExecutable = $worktreePython
    } elseif (Test-Path -LiteralPath $mainPython) {
        $PythonExecutable = $mainPython
    } else {
        $PythonExecutable = "python"
    }
}

$arguments = @("-m", "alphapilot.formal_validation.freqtrade_io_fixture")
if ($FixtureRoot) {
    $arguments += @("--fixture-root", $FixtureRoot)
}
if ($EvidenceRoot) {
    $arguments += @("--evidence-root", $EvidenceRoot)
}
if ($ForbiddenLockedOosRoot) {
    $arguments += @("--forbidden-locked-oos-root", $ForbiddenLockedOosRoot)
}

Push-Location $repoRoot
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"
    & $PythonExecutable @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 2 Freqtrade I/O fixture evidence failed with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
