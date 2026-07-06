param(
  [int]$SignalLimit = 120,
  [int]$ObservationLimit = 120
)

$ErrorActionPreference = "Stop"

Write-Host "Building AlphaPilot V13.7.1 runtime contract files..."
python -m alphapilot.reports.generate_v13_7_1_runtime_contract `
  --signal-limit $SignalLimit `
  --observation-limit $ObservationLimit

Write-Host "Generated:"
Write-Host "  reports/runtime_status.json"
Write-Host "  reports/signal_tape.json"
Write-Host "  reports/paper_observation_ledger.json"

