param(
    [switch]$Continuous,
    [int]$MaxCycles = 1,
    [int]$IntervalSeconds = 300,
    [string]$StateRoot = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw "Python runtime not found. Create .venv or add python to PATH."
    }
    $pythonPath = $pythonCommand.Source
}
if ([string]::IsNullOrWhiteSpace($StateRoot)) {
    $StateRoot = Join-Path $repoRoot "reports\background_research\v35"
}

$arguments = @(
    "-m", "alphapilot.scripts.run_v35_standard_replication_service",
    "--repo-root", $repoRoot,
    "--state-root", $StateRoot,
    "--enqueue-default"
)
$programRoot = Get-ChildItem (Join-Path $repoRoot "reports\dual_track") -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if ($null -ne $programRoot) {
    $arguments += @("--program-root", $programRoot.FullName)
}
if ($Continuous) {
    if ($MaxCycles -le 0) {
        throw "Continuous mode requires MaxCycles greater than zero."
    }
    $arguments += @(
        "--max-cycles", $MaxCycles,
        "--interval-seconds", $IntervalSeconds
    )
}
else {
    $arguments += "--once"
}

& $pythonPath @arguments
exit $LASTEXITCODE
