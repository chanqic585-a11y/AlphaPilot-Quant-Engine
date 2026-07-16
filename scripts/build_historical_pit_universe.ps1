param(
    [string]$DataRoot,
    [string]$CheckedAt = "2026-07-16T00:00:00Z",
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
    "alphapilot.scripts.build_historical_pit_universe",
    "--repo-root",
    $repoRoot,
    "--checked-at",
    $CheckedAt
)
if ($DataRoot) {
    $arguments += @("--data-root", $DataRoot)
}
if ($Run) {
    $arguments += "--run"
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Historical PIT build command failed with exit code $LASTEXITCODE."
}
