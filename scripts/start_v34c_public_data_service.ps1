[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ProgramRoot,

    [Parameter(Mandatory = $true)]
    [string]$BaseSnapshotId,

    [string]$WarehouseRoot = 'D:\Codex-Workspace\回测数据',
    [string]$Instruments = 'BTC-USDT-SWAP,ETH-USDT-SWAP,SOL-USDT-SWAP',
    [ValidateSet('once', 'loop')]
    [string]$Mode = 'loop',
    [double]$SleepSeconds = 30,
    [Nullable[int]]$MaxCycles,
    [string]$PauseFile,
    [string]$PythonPath = $env:ALPHAPILOT_PYTHON
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path -Parent $PSScriptRoot

if (-not $PythonPath) {
    $candidates = @(
        (Join-Path $repositoryRoot '.venv\Scripts\python.exe'),
        'D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe'
    )
    $PythonPath = $candidates | Where-Object {
        Test-Path -LiteralPath $_ -PathType Leaf
    } | Select-Object -First 1
}
if (-not $PythonPath -or -not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw 'AlphaPilot Python runtime not found. Pass -PythonPath or set ALPHAPILOT_PYTHON.'
}

$arguments = @(
    '-m', 'alphapilot.scripts.run_v34c_okx_public_data_service',
    '--warehouse-root', $WarehouseRoot,
    '--program-root', $ProgramRoot,
    '--base-snapshot-id', $BaseSnapshotId,
    '--instruments', $Instruments,
    '--mode', $Mode,
    '--sleep-seconds', [string]$SleepSeconds
)
if ($null -ne $MaxCycles) {
    $arguments += @('--max-cycles', [string]$MaxCycles)
}
if ($PauseFile) {
    $arguments += @('--pause-file', $PauseFile)
}

Push-Location $repositoryRoot
try {
    & $PythonPath @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "V34C public-data service exited with code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
