param(
    [string]$RunId,
    [string]$StrategyName,
    [switch]$SmokeOnly,
    [string]$WarehouseRoot = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$warehouseName = -join ([char[]](0x56DE, 0x6D4B, 0x6570, 0x636E))
if (-not $WarehouseRoot) {
    $WarehouseRoot = Join-Path 'D:\Codex-Workspace' $warehouseName
}
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Quant Engine Python environment is missing: $python"
}

if (-not $RunId) {
    & $python -m alphapilot.evolution.workflow.cli bootstrap | Out-Null
    $resolveArguments = @(
        '-m',
        'alphapilot.evolution.workflow.cli',
        'resolve-backtest-run'
    )
    if ($StrategyName) {
        $resolveArguments += @('--strategy-name', $StrategyName)
    }
    $resolvedJson = & $python @resolveArguments
    if ($LASTEXITCODE -ne 0) {
        throw 'No matching backtest workflow was found.'
    }
    $resolved = $resolvedJson | ConvertFrom-Json
    $RunId = [string]$resolved.workflowRunId
}

$command = if ($SmokeOnly) { 'research-smoke' } else { 'one-click-backtest' }
& $python -m alphapilot.evolution.workflow.cli `
    --warehouse-root $WarehouseRoot `
    $command --run-id $RunId
if ($LASTEXITCODE -ne 0) {
    throw "V13.27.1.1 workflow failed with exit code $LASTEXITCODE"
}
