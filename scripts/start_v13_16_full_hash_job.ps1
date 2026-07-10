param(
  [string]$PythonPath = ".venv\Scripts\python.exe",
  [switch]$Worker
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$jobRoot = Join-Path $repoRoot "data\market\jobs\v13_16_full_hash"
$manifestPath = Join-Path $jobRoot "job_manifest.json"
$stdoutPath = Join-Path $jobRoot "stdout.log"
$stderrPath = Join-Path $jobRoot "stderr.log"
$resolvedPython = if ([System.IO.Path]::IsPathRooted($PythonPath)) { $PythonPath } else { Join-Path $repoRoot $PythonPath }
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Write-JobManifest([hashtable]$Value) {
  [System.IO.Directory]::CreateDirectory($jobRoot) | Out-Null
  $temporary = "$manifestPath.tmp"
  $json = $Value | ConvertTo-Json -Depth 8
  [System.IO.File]::WriteAllText($temporary, $json + [Environment]::NewLine, $utf8)
  if (Test-Path -LiteralPath $manifestPath) {
    Remove-Item -LiteralPath $manifestPath -Force
  }
  Move-Item -LiteralPath $temporary -Destination $manifestPath -Force
}

function Read-JobManifest {
  if (-not (Test-Path -LiteralPath $manifestPath)) { return $null }
  return Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

if (-not $Worker) {
  $existing = Read-JobManifest
  if ($existing -and $existing.status -eq "running" -and $existing.workerPid) {
    $running = Get-Process -Id ([int]$existing.workerPid) -ErrorAction SilentlyContinue
    if ($running) {
      Write-Output "V13.16 full hash job is already running (PID $($existing.workerPid))."
      Write-Output "Manifest: $manifestPath"
      exit 0
    }
  }
  [System.IO.Directory]::CreateDirectory($jobRoot) | Out-Null
  $process = Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", $PSCommandPath,
    "-PythonPath", $PythonPath,
    "-Worker"
  ) -WindowStyle Hidden -PassThru
  Write-Output "Started V13.16 full hash worker PID $($process.Id)."
  Write-Output "Manifest: $manifestPath"
  Write-Output "Stdout: $stdoutPath"
  Write-Output "Stderr: $stderrPath"
  exit 0
}

if (-not (Test-Path -LiteralPath $resolvedPython)) {
  throw "Python runtime not found: $resolvedPython"
}

$startedAt = (Get-Date).ToUniversalTime().ToString("o")
$manifest = @{
  schemaVersion = "alphapilot_background_job_v1"
  jobId = "v13_16_full_hash"
  status = "running"
  workerPid = $PID
  startedAt = $startedAt
  completedAt = $null
  exitCode = $null
  checkpointPath = "data/market/checkpoints/catalog_hash_checkpoint.json"
  reportPath = "reports/v13_16_data_foundation_report.json"
  stdoutPath = "data/market/jobs/v13_16_full_hash/stdout.log"
  stderrPath = "data/market/jobs/v13_16_full_hash/stderr.log"
}

if (Test-Path -LiteralPath $manifestPath) {
  [System.IO.File]::Delete($manifestPath)
}
Write-JobManifest $manifest

$arguments = @(
  "-m", "alphapilot.reports.generate_v13_16_data_foundation_report",
  "--market-root", "data/market",
  "--registry-path", "data/evolution_registry.sqlite",
  "--symbols", "BTC,ETH,SOL",
  "--timeframes", "15m,1h,4h,1d",
  "--market-type", "swap",
  "--exchange", "unknown",
  "--hash-mode", "all",
  "--output-json", "reports/v13_16_data_foundation_report.json",
  "--output-markdown", "reports/v13_16_data_foundation_summary.md"
)

Push-Location $repoRoot
try {
  $pythonProcess = Start-Process -FilePath $resolvedPython -ArgumentList $arguments -WindowStyle Hidden -PassThru -Wait -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
  $exitCode = $pythonProcess.ExitCode
}
catch {
  $_ | Out-String | Out-File -LiteralPath $stderrPath -Encoding UTF8 -Append
  $exitCode = 1
}
finally {
  Pop-Location
}

$manifest.status = if ($exitCode -eq 0) { "completed" } else { "failed" }
$manifest.completedAt = (Get-Date).ToUniversalTime().ToString("o")
$manifest.exitCode = $exitCode
Write-JobManifest $manifest
exit $exitCode
