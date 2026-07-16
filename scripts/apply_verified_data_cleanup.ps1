param(
    [string]$DataRoot,
    [string]$PlanPath = "reports/storage_governance/cleanup_dry_run.json",
    [string]$OutputRoot = "reports/storage_governance",
    [switch]$ApplyCleanup
)

$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$env:PYTHONIOENCODING = "utf-8"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workspaceRoot = "D:\Codex-Workspace"
$dataLeaf = -join @([char]0x56DE, [char]0x6D4B, [char]0x6570, [char]0x636E)
$authorizedDataRoot = [System.IO.Path]::GetFullPath((Join-Path $workspaceRoot $dataLeaf)).TrimEnd('\')
if ([string]::IsNullOrWhiteSpace($DataRoot)) {
    $DataRoot = $authorizedDataRoot
}
$resolvedDataRoot = [System.IO.Path]::GetFullPath($DataRoot).TrimEnd('\')
if ($resolvedDataRoot -ne $authorizedDataRoot) {
    throw "Cleanup is locked to the authorized data root: $authorizedDataRoot"
}
if (-not $ApplyCleanup) {
    throw "No deletion was performed. Re-run with -ApplyCleanup only after reviewing the dry-run plan."
}

$venvCandidates = @(
    (Join-Path $repoRoot ".venv\Scripts\python.exe"),
    (Join-Path $workspaceRoot "AlphaPilot-Quant-Engine\.venv\Scripts\python.exe")
)
$python = $venvCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) {
    throw "No AlphaPilot Quant virtualenv Python found."
}
$resolvedPlanPath = if ([System.IO.Path]::IsPathRooted($PlanPath)) {
    [System.IO.Path]::GetFullPath($PlanPath)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $repoRoot $PlanPath))
}
$resolvedOutputRoot = if ([System.IO.Path]::IsPathRooted($OutputRoot)) {
    [System.IO.Path]::GetFullPath($OutputRoot)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputRoot))
}
if (-not (Test-Path -LiteralPath $resolvedPlanPath -PathType Leaf)) {
    throw "Reviewed cleanup plan not found: $resolvedPlanPath"
}

Push-Location $repoRoot
try {
    & $python -m alphapilot.storage_governance.cleanup_executor `
        --data-root $resolvedDataRoot `
        --plan $resolvedPlanPath `
        --output-root $resolvedOutputRoot `
        --apply-cleanup
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($exitCode -ne 0) {
    throw "Verified storage cleanup failed with exit code $exitCode."
}

Write-Host "Verified cleanup complete inside: $resolvedDataRoot" -ForegroundColor Green
Write-Host "Manifest: $(Join-Path $resolvedOutputRoot 'cleanup_apply_manifest.json')"
