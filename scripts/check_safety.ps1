param(
  [switch]$IncludeDocumentation,
  [switch]$ShowAllMatches
)

$patterns = @(
  "apiSecret",
  "passphrase",
  "exchangeKey",
  "withdraw",
  "createOrder",
  "cancelOrder",
  "fetchBalance",
  "fetchPositions",
  "private",
  "trade api",
  "withdraw api",
  "place order",
  "execute trade",
  "auto trade",
  "真实下单",
  "自动交易"
)

$root = Resolve-Path "."
$scanRoots = @(
  "alphapilot",
  "scripts",
  "tests",
  "user_data\config",
  "user_data\freqaimodels",
  "user_data\hyperopts",
  "user_data\notebooks",
  "user_data\strategies"
)
if ($IncludeDocumentation) {
  $scanRoots += @("docs", "reports")
}
$textExtensions = @(
  ".py", ".ps1", ".psm1", ".cmd", ".bat", ".sh",
  ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".example", ".ipynb"
)
$fileMap = @{}
foreach ($relativeRoot in $scanRoots) {
  $scanRoot = Join-Path $root $relativeRoot
  if (-not (Test-Path -LiteralPath $scanRoot)) { continue }
  foreach ($file in Get-ChildItem -LiteralPath $scanRoot -Recurse -File) {
    if (
      $file.FullName -notmatch "__pycache__" -and
      $file.FullName -notmatch "\\.pytest_cache\\" -and
      $file.Extension.ToLowerInvariant() -in $textExtensions -and
      $file.Name -ne "check_safety.ps1"
    ) {
      $fileMap[$file.FullName] = $file
    }
  }
}
foreach ($file in Get-ChildItem -LiteralPath $root -File) {
  if ($file.Extension.ToLowerInvariant() -in $textExtensions) {
    $fileMap[$file.FullName] = $file
  }
}
$files = @($fileMap.Values)

$rawMatches = if ($files.Count -gt 0) {
  Select-String -LiteralPath @($files.FullName) -Pattern $patterns -SimpleMatch -CaseSensitive:$false
} else { @() }
$matches = @($rawMatches | ForEach-Object {
  [PSCustomObject]@{
    Path = $_.Path
    Line = $_.LineNumber
    Text = $_.Line.Trim()
  }
})

if ($matches) {
  $uniqueFileCount = @($matches.Path | Sort-Object -Unique).Count
  Write-Host "Safety scan found $($matches.Count) term matches across $uniqueFileCount files. Review context; test fixtures and negative statements are allowed."
  $displayMatches = if ($ShowAllMatches) { $matches } else { @($matches | Select-Object -First 100) }
  $displayMatches | Format-Table -AutoSize
  if (-not $ShowAllMatches -and $matches.Count -gt $displayMatches.Count) {
    Write-Host "Showing first $($displayMatches.Count) matches. Use -ShowAllMatches for the complete list."
  }
} else {
  Write-Host "Safety scan found no matching terms."
}

Write-Host "Safety scan completed. Review any executable integration against the current release boundary."
