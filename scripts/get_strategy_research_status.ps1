param([string]$StateRoot = "")

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($StateRoot)) {
    $StateRoot = Join-Path $repoRoot "reports\background_research\v35"
}
$healthPath = Join-Path $StateRoot "health.json"
if (-not (Test-Path -LiteralPath $healthPath)) {
    Write-Output "AlphaPilot V35 research has not written health.json yet."
    exit 1
}
$health = Get-Content -LiteralPath $healthPath -Raw -Encoding utf8 | ConvertFrom-Json
$health | Select-Object checkedAt, serviceStatus, campaignCount, formalRunCount, lockedOosReadCount, releaseCount, demoReleaseCount, demoArm, orderCount | Format-List
