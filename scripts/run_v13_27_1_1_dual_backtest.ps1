param(
    [string]$RunId,
    [string]$StrategyName,
    [switch]$SmokeOnly,
    [string]$WarehouseRoot = 'D:\Codex-Workspace\回测数据'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Quant Engine Python environment is missing: $python"
}

if (-not $RunId) {
    & $python -m alphapilot.evolution.workflow.cli bootstrap | Out-Null
    $projectionJson = & $python -m alphapilot.evolution.workflow.cli projection
    $projection = $projectionJson | ConvertFrom-Json
    $eligible = @($projection.items | Where-Object {
        $_.stage -eq 'backtest' -and
        (-not $StrategyName -or $_.displayName -eq $StrategyName)
    })
    if ($eligible.Count -eq 0) {
        throw 'No matching backtest workflow was found.'
    }
    $RunId = [string]$eligible[0].workflowRunId
}

$command = if ($SmokeOnly) { 'research-smoke' } else { 'one-click-backtest' }
& $python -m alphapilot.evolution.workflow.cli `
    --warehouse-root $WarehouseRoot `
    $command --run-id $RunId
if ($LASTEXITCODE -ne 0) {
    throw "V13.27.1.1 workflow failed with exit code $LASTEXITCODE"
}
