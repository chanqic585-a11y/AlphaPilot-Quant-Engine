param(
    [string]$DataRoot,
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
    "alphapilot.scripts.collect_formal_derivatives_data",
    "--repo-root",
    $repoRoot
)
if ($DataRoot) {
    $arguments += @("--data-root", $DataRoot)
}
if ($Run) {
    $arguments += "--run"
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Formal derivatives-data collection command failed with exit code $LASTEXITCODE."
}
