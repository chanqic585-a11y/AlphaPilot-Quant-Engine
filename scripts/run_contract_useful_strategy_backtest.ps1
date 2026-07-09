param(
  [string]$DataDir = "user_data/data/local_contract_xlsx/okx",
  [string]$Timerange = "20200101-",
  [string]$Pairs = "GAS/USDT:USDT,ZRX/USDT:USDT,DOGE/USDT:USDT,CRO/USDT:USDT,ICX/USDT:USDT,APE/USDT:USDT,APT/USDT:USDT,BTC/USDT:USDT,GALA/USDT:USDT,LTC/USDT:USDT,MANA/USDT:USDT,NEAR/USDT:USDT,SAND/USDT:USDT,SOL/USDT:USDT,TRX/USDT:USDT,ADA/USDT:USDT,AXS/USDT:USDT",
  [string]$Strategies = "AlphaPilotBatchB_EMATrendShort4H,AlphaPilotLowFrequencyDirectional4HV01,BenchmarkRSIMeanReversion,AlphaPilotBatchH_VolatilityCompressionBreakout4H,AlphaPilotBatchD_BreakdownRetestShort4H,AlphaPilotShortRejection1HV01",
  [int]$PairChunkSize = 17,
  [switch]$Resume,
  [switch]$Run
)

$ErrorActionPreference = "Stop"

$BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$PythonExe = if ($env:ALPHAPILOT_PYTHON) {
  $env:ALPHAPILOT_PYTHON
} elseif (Test-Path -LiteralPath $BundledPython) {
  $BundledPython
} else {
  "python"
}

$pythonArgs = @(
  "-m",
  "alphapilot.backtesting.external_5m_batch_runner",
  "--data-dir",
  $DataDir,
  "--timerange",
  $Timerange,
  "--pairs",
  $Pairs,
  "--pair-chunk-size",
  [string]$PairChunkSize,
  "--strategies",
  $Strategies,
  "--output-prefix",
  "contract_useful_strategy",
  "--manifest-path",
  "reports/contract_useful_strategy_backtest_manifest.json",
  "--summary-path",
  "reports/contract_useful_strategy_backtest_summary.json",
  "--log-dir",
  "reports/contract_useful_strategy_backtest_logs"
)

if ($Run) {
  $pythonArgs += "--run"
}
if ($Resume) {
  $pythonArgs += "--resume"
}

Write-Host "AlphaPilot contract XLSX useful-strategy backtest"
Write-Host "DataDir: $DataDir"
Write-Host "Timerange: $Timerange"
Write-Host "Pairs: $Pairs"
Write-Host "Strategies: $Strategies"
Write-Host "Research backtest only. No Dry-run, no live trading, no private API, no orders."
& $PythonExe @pythonArgs
