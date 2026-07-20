param(
    [int]$MaxCycles = 288,
    [int]$IntervalSeconds = 300,
    [string]$StateRoot = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot "run_strategy_research_cycle.ps1"
if ([string]::IsNullOrWhiteSpace($StateRoot)) {
    $StateRoot = Join-Path $repoRoot "reports\background_research\v35"
}
$StateRoot = [System.IO.Path]::GetFullPath($StateRoot)
New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null

$stdoutPath = Join-Path $StateRoot "background.stdout.log"
$stderrPath = Join-Path $StateRoot "background.stderr.log"
$argumentList = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", ('"' + $runner + '"'),
    "-Continuous",
    "-MaxCycles", $MaxCycles,
    "-IntervalSeconds", $IntervalSeconds,
    "-StateRoot", ('"' + $StateRoot + '"')
)
$startParameters = @{
    FilePath = "powershell.exe"
    ArgumentList = $argumentList
    WorkingDirectory = $repoRoot
    WindowStyle = "Hidden"
    RedirectStandardOutput = $stdoutPath
    RedirectStandardError = $stderrPath
    PassThru = $true
}
$process = Start-Process @startParameters

Set-Content -LiteralPath (Join-Path $StateRoot "background.pid") -Value $process.Id -Encoding ascii
Write-Output "AlphaPilot V35 background research started. PID: $($process.Id)"
Write-Output "State: $StateRoot"
