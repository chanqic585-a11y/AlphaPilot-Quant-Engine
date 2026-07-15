param(
    [switch]$Run,
    [string]$VibePath = "D:\Codex-Workspace\external\Vibe-Trading",
    [string]$Alpha101Path = "D:\Codex-Workspace\external\alpha101",
    [string]$Alpha191Path = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $Alpha191Path) {
    $Alpha191File = Get-ChildItem `
        -LiteralPath (Join-Path $env:APPDATA "Microsoft\Windows\Network Shortcuts") `
        -Filter "Alpha191*.pdf" `
        -File | Select-Object -First 1
    if (-not $Alpha191File) { throw "Alpha191 PDF was not found." }
    $Alpha191Path = $Alpha191File.FullName
}
$PythonCandidates = @(
    $env:ALPHAPILOT_PYTHON,
    (Join-Path $RepoRoot ".venv\Scripts\python.exe"),
    (Join-Path $RepoRoot "..\..\.venv\Scripts\python.exe")
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

Write-Host "External research audit plan (offline, read-only):"
Write-Host "- Vibe-Trading: $VibePath"
Write-Host "- alpha101: $Alpha101Path"
Write-Host "- Alpha191 manual: $Alpha191Path"
if (-not $Run) {
    Write-Host "Dry run only. Add -Run to write frozen manifests."
    exit 0
}
if (-not $PythonCandidates) {
    throw "No AlphaPilot Python runtime found. Set ALPHAPILOT_PYTHON."
}
$Python = @($PythonCandidates)[0]

Push-Location $RepoRoot
try {
    & $Python -m alphapilot.external_research.audit `
        --vibe-path $VibePath `
        --alpha101-path $Alpha101Path `
        --alpha191-path $Alpha191Path
    if ($LASTEXITCODE -ne 0) { throw "External research audit failed." }
} finally {
    Pop-Location
}
