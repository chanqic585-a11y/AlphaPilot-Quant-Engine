param([string]$StateRoot = "")

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($StateRoot)) {
    $StateRoot = Join-Path $repoRoot "reports\background_research\v35"
}
Remove-Item -LiteralPath (Join-Path $StateRoot "PAUSE") -Force -ErrorAction SilentlyContinue
Write-Output "AlphaPilot V35 research resume requested."
