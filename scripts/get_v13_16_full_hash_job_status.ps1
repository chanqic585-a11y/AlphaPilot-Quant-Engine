param()

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$manifestPath = Join-Path $repoRoot "data\market\jobs\v13_16_full_hash\job_manifest.json"
$checkpointPath = Join-Path $repoRoot "data\market\checkpoints\catalog_hash_checkpoint.json"
$totalFiles = 12473

function Read-SharedUtf8([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return $null }
  $share = [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
  $stream = New-Object System.IO.FileStream($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, $share)
  try {
    $reader = New-Object System.IO.StreamReader($stream, [System.Text.Encoding]::UTF8, $true)
    try { return $reader.ReadToEnd() }
    finally { $reader.Dispose() }
  }
  finally { $stream.Dispose() }
}

$manifestText = Read-SharedUtf8 $manifestPath
$checkpointText = Read-SharedUtf8 $checkpointPath
$manifest = if ($manifestText) { $manifestText | ConvertFrom-Json } else { $null }
$checkpoint = if ($checkpointText) { $checkpointText | ConvertFrom-Json } else { $null }
$cachedFiles = if ($checkpoint -and $checkpoint.files) { @($checkpoint.files.PSObject.Properties).Count } else { 0 }
$workerRunning = $false
if ($manifest -and $manifest.workerPid) {
  $workerRunning = [bool](Get-Process -Id ([int]$manifest.workerPid) -ErrorAction SilentlyContinue)
}

[pscustomobject]@{
  JobStatus = if ($manifest) { $manifest.status } else { "not_started" }
  WorkerPid = if ($manifest) { $manifest.workerPid } else { $null }
  WorkerRunning = $workerRunning
  CachedFiles = $cachedFiles
  TotalFiles = $totalFiles
  ProgressPercent = [math]::Round($cachedFiles / $totalFiles * 100, 2)
  StartedAt = if ($manifest) { $manifest.startedAt } else { $null }
  CompletedAt = if ($manifest) { $manifest.completedAt } else { $null }
  ExitCode = if ($manifest) { $manifest.exitCode } else { $null }
} | Format-List
