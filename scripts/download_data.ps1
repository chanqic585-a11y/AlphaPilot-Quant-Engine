param(
  [switch]$Run
)

$pairs = @(
  "BTC/USDT:USDT",
  "ETH/USDT:USDT"
) -join " "

$command = "docker compose run --rm freqtrade download-data --exchange okx --pairs $pairs --timeframes 15m 1h 4h --timerange 20240101-"

Write-Host "AlphaPilot V13.2 data download command template:"
Write-Host $command
Write-Host "TODO: confirm any Freqtrade futures-specific arguments before running large downloads."

if ($Run) {
  Invoke-Expression $command
} else {
  Write-Host "Dry preview only. Re-run with -Run to execute."
}
