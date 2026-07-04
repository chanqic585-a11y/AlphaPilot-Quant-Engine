param(
  [switch]$Run
)

$command = "docker compose run --rm freqtrade backtesting --config user_data/config/config.backtest.json --strategy AlphaPilotVolumeReboundV01 --timerange 20240101-20240701 -i 15m"

Write-Host "AlphaPilot V13.2 backtest command template:"
Write-Host $command

if ($Run) {
  Invoke-Expression $command
} else {
  Write-Host "Dry preview only. Re-run with -Run to execute."
}
