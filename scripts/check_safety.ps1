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
$files = Get-ChildItem -Path $root -Recurse -File |
  Where-Object {
    $_.FullName -notmatch "\\.git\\" -and
    $_.FullName -notmatch "__pycache__" -and
    $_.Extension -ne ".pyc" -and
    $_.FullName -notmatch "\\user_data\\data\\" -and
    $_.FullName -notmatch "\\user_data\\backtest_results\\" -and
    $_.FullName -notmatch "\\user_data\\logs\\" -and
    $_.Name -ne "check_safety.ps1"
  }

$matches = foreach ($file in $files) {
  Select-String -Path $file.FullName -Pattern $patterns -SimpleMatch -CaseSensitive:$false |
    ForEach-Object {
      [PSCustomObject]@{
        Path = $_.Path
        Line = $_.LineNumber
        Text = $_.Line.Trim()
      }
    }
}

if ($matches) {
  Write-Host "Safety scan found terms. Review context below; V13.4 allows safety docs and negative statements only."
  $matches | Format-Table -AutoSize
} else {
  Write-Host "Safety scan found no matching terms."
}

Write-Host "Safety scan completed. No executable trade integration is expected in V13.4."
