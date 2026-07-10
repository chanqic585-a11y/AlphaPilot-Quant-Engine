param(
  [string]$PythonPath = ".venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$resolvedPython = if ([System.IO.Path]::IsPathRooted($PythonPath)) { $PythonPath } else { Join-Path $repoRoot $PythonPath }
if (-not (Test-Path -LiteralPath $resolvedPython)) {
  throw "Python runtime not found: $resolvedPython"
}

Push-Location $repoRoot
try {
  & $resolvedPython -m alphapilot.reports.seed_v13_16_canonical_metadata
  $exitCode = $LASTEXITCODE
}
finally {
  Pop-Location
}
if ($exitCode -ne 0) {
  throw "V13.16 canonical metadata seed failed with exit code $exitCode"
}
