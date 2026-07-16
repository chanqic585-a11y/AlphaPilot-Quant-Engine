param(
    [string]$GitCommit = "unknown",
    [string]$EnvironmentHash = "unavailable",
    [string]$CreatedAt = "2026-07-16T00:00:00Z",
    [switch]$Run
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$worktreeMain = Split-Path (Split-Path $repoRoot -Parent) -Parent
$worktreeMainPython = Join-Path $worktreeMain ".venv\Scripts\python.exe"
$python = @($venvPython, $worktreeMainPython) |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1
if (-not $python) {
    throw "No project virtualenv Python found. Run the repository runtime setup first."
}
$arguments = @(
    "-m",
    "alphapilot.scripts.freeze_derivatives_snapshot",
    "--repo-root",
    $repoRoot,
    "--git-commit",
    $GitCommit,
    "--environment-hash",
    $EnvironmentHash,
    "--created-at",
    $CreatedAt
)
if ($Run) {
    $arguments += "--run"
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Derivatives snapshot freeze failed with exit code $LASTEXITCODE."
}
