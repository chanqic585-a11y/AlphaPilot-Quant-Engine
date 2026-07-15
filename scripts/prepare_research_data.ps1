param(
    [switch]$AuditOnly,
    [switch]$Collect,
    [switch]$Normalize,
    [switch]$BuildDerived,
    [switch]$FreezeSnapshot
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $gitCommonDir = (& git -C $repo rev-parse --git-common-dir).Trim()
    if (-not [IO.Path]::IsPathRooted($gitCommonDir)) {
        $gitCommonDir = [IO.Path]::GetFullPath((Join-Path $repo $gitCommonDir))
    }
    $mainRepo = Split-Path -Parent $gitCommonDir
    $python = Join-Path $mainRepo '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $python)) {
    throw "Project Python environment is missing in the worktree and main repository."
}
$arguments = @('-m', 'alphapilot.research_screening.prepare_data', '--repo-root', $repo)
if ($Collect) {
    $arguments += '--collect'
}
& $python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Research data preparation failed with exit code $LASTEXITCODE"
}
