param(
    [string]$DataRoot,
    [string]$OutputRoot = "reports/storage_governance"
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
    throw "Storage governance is locked to the authorized data root: $authorizedDataRoot"
}
if (-not (Test-Path -LiteralPath $resolvedDataRoot -PathType Container)) {
    throw "Authorized data root does not exist: $resolvedDataRoot"
}

$venvCandidates = @(
    (Join-Path $repoRoot ".venv\Scripts\python.exe"),
    (Join-Path $workspaceRoot "AlphaPilot-Quant-Engine\.venv\Scripts\python.exe")
)
$python = $venvCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) {
    throw "No AlphaPilot Quant virtualenv Python found."
}

$resolvedOutputRoot = if ([System.IO.Path]::IsPathRooted($OutputRoot)) {
    [System.IO.Path]::GetFullPath($OutputRoot)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputRoot))
}
$referenceRoots = @(
    $repoRoot,
    (Join-Path $workspaceRoot "AlphaPilot-Control-Console"),
    (Join-Path $workspaceRoot "AlphaPilot-Docs"),
    (Join-Path $workspaceRoot "trade-discipline-journal")
) | Where-Object { Test-Path -LiteralPath $_ -PathType Container }

$arguments = @(
    "-m", "alphapilot.storage_governance.cleanup_planner",
    "--data-root", $resolvedDataRoot,
    "--output-root", $resolvedOutputRoot
)
foreach ($referenceRoot in $referenceRoots) {
    $arguments += @("--repo-root", $referenceRoot)
}

Push-Location $repoRoot
try {
    & $python @arguments
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($exitCode -ne 0) {
    throw "Storage cleanup audit failed with exit code $exitCode."
}

Write-Host "Dry-run complete. No files were deleted." -ForegroundColor Green
Write-Host "Plan: $(Join-Path $resolvedOutputRoot 'cleanup_dry_run.json')"
