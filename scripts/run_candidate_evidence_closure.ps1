param(
    [ValidateSet('preregister', 'validate')]
    [string]$Phase = 'preregister',
    [string]$SourceRoot = 'D:\Codex-Workspace\AlphaPilot-Quant-Engine'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $SourceRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Pinned Quant Python not found: $Python"
}

& $Python -m alphapilot.reports.generate_candidate_evidence_closure_report `
    --phase $Phase `
    --root $RepoRoot `
    --source-root $SourceRoot
if ($LASTEXITCODE -ne 0) {
    throw "Candidate evidence closure phase failed: $Phase"
}
