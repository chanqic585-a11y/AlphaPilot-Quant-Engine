param()

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    $gitCommonDir = (& git -C $repo rev-parse --git-common-dir).Trim()
    if (-not [IO.Path]::IsPathRooted($gitCommonDir)) {
        $gitCommonDir = [IO.Path]::GetFullPath((Join-Path $repo $gitCommonDir))
    }
    $python = Join-Path (Split-Path -Parent $gitCommonDir) '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Project Python environment is missing.'
}
& $python -m alphapilot.research_screening.run_factor_benchmark --repo-root $repo
if ($LASTEXITCODE -ne 0) {
    throw "Factor benchmark failed or Phase 3B remained blocked with exit code $LASTEXITCODE"
}
