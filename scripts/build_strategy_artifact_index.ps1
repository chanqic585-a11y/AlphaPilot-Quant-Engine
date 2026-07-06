param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

& $Python -m alphapilot.reports.generate_v13_7_4_strategy_artifact_index
if ($LASTEXITCODE -ne 0) {
    throw "Strategy artifact index generation failed."
}

