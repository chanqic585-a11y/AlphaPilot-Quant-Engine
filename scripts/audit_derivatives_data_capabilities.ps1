param(
    [string]$DataRoot,
    [string]$CheckedAt,
    [switch]$Run
)

$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
chcp.com 65001 > $null
$env:PYTHONIOENCODING = "utf-8"
if ([string]::IsNullOrWhiteSpace($DataRoot)) {
    $dataLeaf = -join @([char]0x56DE, [char]0x6D4B, [char]0x6570, [char]0x636E)
    $DataRoot = Join-Path "D:\Codex-Workspace" $dataLeaf
}
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
    "alphapilot.scripts.generate_v13_27_1_12_data_readiness",
    "--repo-root",
    $repoRoot,
    "--data-root",
    $DataRoot
)
if ($CheckedAt) {
    $arguments += @("--checked-at", $CheckedAt)
}
if ($Run) {
    $arguments += "--run"
}

& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "V13.27.1.12 derivatives-data capability audit failed with exit code $LASTEXITCODE."
}
