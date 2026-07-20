param([string]$StateRoot = "")

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($StateRoot)) {
    $StateRoot = Join-Path $repoRoot "reports\background_research\v35"
}
New-Item -ItemType Directory -Path $StateRoot -Force | Out-Null
Set-Content -LiteralPath (Join-Path $StateRoot "PAUSE") -Value "operator_pause" -Encoding utf8
Write-Output "AlphaPilot V35 research pause requested."
