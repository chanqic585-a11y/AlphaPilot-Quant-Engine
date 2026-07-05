param(
    [string]$Hypotheses = "reports/v13_4_25_research_hypotheses.json",
    [string]$FactorPanel = "",
    [string]$Timerange = "20260101-",
    [string]$Timeframe = "1h",
    [string]$Horizons = "4,8,12,24",
    [double]$TpPct = 0.05,
    [double]$SlPct = 0.025
)

$ErrorActionPreference = "Stop"

$argsList = @(
    "-m", "alphapilot.research_factory.validate_hypotheses",
    "--hypotheses", $Hypotheses,
    "--timerange", $Timerange,
    "--timeframe", $Timeframe,
    "--horizons", $Horizons,
    "--tp-pct", "$TpPct",
    "--sl-pct", "$SlPct"
)

if ($FactorPanel -ne "") {
    $argsList += @("--factor-panel", $FactorPanel)
}

Write-Host "Running research-only hypothesis validation..."
Write-Host "No Freqtrade backtest, Dry-run, Trade API, Withdraw API, API key, account read, order, or auto trading is used."
python @argsList
