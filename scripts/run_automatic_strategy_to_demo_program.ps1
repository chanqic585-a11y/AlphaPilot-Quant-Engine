param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('v19')]
    [string]$Stage,
    [Parameter(Mandatory = $true)]
    [string]$ProgramId,
    [Parameter(Mandatory = $true)]
    [string]$BaselineCommit,
    [Parameter(Mandatory = $true)]
    [string]$ProgramSpecHash,
    [Parameter(Mandatory = $true)]
    [string]$GeneratedAt,
    [Parameter(Mandatory = $true)]
    [string]$Catalog,
    [Parameter(Mandatory = $true)]
    [string]$SourceAudit,
    [Parameter(Mandatory = $true)]
    [string]$Snapshot,
    [string[]]$BaselineArtifact = @(),
    [string]$Python = 'python'
)

$ErrorActionPreference = 'Stop'
$arguments = @(
    '-m', 'alphapilot.scripts.run_automatic_strategy_demo',
    '--stage', $Stage,
    '--program-id', $ProgramId,
    '--baseline-commit', $BaselineCommit,
    '--program-spec-hash', $ProgramSpecHash,
    '--generated-at', $GeneratedAt,
    '--catalog', $Catalog,
    '--source-audit', $SourceAudit,
    '--snapshot', $Snapshot
)
foreach ($artifact in $BaselineArtifact) {
    $arguments += @('--baseline-artifact', $artifact)
}
& $Python @arguments
exit $LASTEXITCODE
