param(
    [switch]$PreRegister,
    [switch]$RunSignalValidation,
    [switch]$RunLockedValidation,
    [switch]$RunRiskModels,
    [switch]$RunAll,
    [ValidateSet('all', 'A', 'B', 'C')]
    [string]$CandidateTier = 'all',
    [string]$SourceRoot = 'D:\Codex-Workspace\AlphaPilot-Quant-Engine'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $SourceRoot '.venv\Scripts\python.exe'

$selectedPlanningLayers = @()
if ($RunSignalValidation) { $selectedPlanningLayers += 'signal layer' }
if ($RunLockedValidation) { $selectedPlanningLayers += 'locked sample and walk-forward' }
if ($RunRiskModels) { $selectedPlanningLayers += 'risk models, cost stress, Monte Carlo, and portfolio risk' }

if ($PreRegister -and $RunAll) {
    throw 'Use -PreRegister or -RunAll, not both.'
}

if ($RunAll -and $CandidateTier -ne 'all') {
    throw '-RunAll must preserve the complete pre-registered candidate set. Use -CandidateTier only when printing a plan.'
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Pinned Quant Python not found: $Python"
}

if ($PreRegister) {
    & $Python -m alphapilot.reports.generate_candidate_evidence_closure_report `
        --phase preregister `
        --root $RepoRoot `
        --source-root $SourceRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'Candidate evidence closure preregistration failed.'
    }
    exit 0
}

if (-not $RunAll) {
    Write-Host 'Candidate Evidence Closure - PLAN ONLY' -ForegroundColor Cyan
    Write-Host "Candidate tier focus: $CandidateTier"
    if ($selectedPlanningLayers.Count -eq 0) {
        Write-Host 'Planned layers: signal, locked sample, walk-forward, costs, risk models, Monte Carlo, and portfolio risk.'
    }
    else {
        Write-Host ("Planned layer focus: " + ($selectedPlanningLayers -join '; ') + '.')
    }
    Write-Host 'No research validation was executed.' -ForegroundColor Yellow
    Write-Host 'Only -RunAll executes the complete locked validation.' -ForegroundColor Yellow
    exit 0
}

Write-Host 'Running the complete immutable candidate set and every locked validation layer.' -ForegroundColor Cyan
& $Python -m alphapilot.reports.generate_candidate_evidence_closure_report `
    --phase all `
    --root $RepoRoot `
    --source-root $SourceRoot
if ($LASTEXITCODE -ne 0) {
    throw 'Candidate evidence closure validation failed.'
}
