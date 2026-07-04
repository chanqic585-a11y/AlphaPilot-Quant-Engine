# AlphaPilot Quant Engine

AlphaPilot Quant Engine is the future backend research and execution-control layer for AlphaPilot.

Current version:

```text
AlphaPilot V13.4 - Real Freqtrade Smoke Backtest Runtime Prep
```

## Positioning

V13.4 prepares real Freqtrade smoke backtest execution and report export on top of the V13.3 strategy implementation.

It is separate from the AlphaPilot Mobile App. The mobile app remains the phone-side AI control panel and manual trade record interface. This repository is the backend quant foundation.

## Safety Boundary

V13.4 does not perform live trading.

- No real Trade API.
- No Withdraw API.
- No real API Key storage.
- No real account reads.
- No real position reads.
- No real order creation.
- No automatic trading.
- No real dry-run execution.
- No public REST API exposure.

All configs are templates for research, backtest preparation, or future dry-run design. Never commit real exchange credentials.

## Why Freqtrade

Freqtrade gives AlphaPilot a practical open-source base for:

- exchange data download
- strategy files
- local backtesting
- dry-run concepts
- structured user_data layout

V13.4 is not a strategy tuning version. It keeps the V13.3 strategy parameters fixed and focuses on the runtime path: data download, Freqtrade backtest, result JSON, and AlphaPilot report export.

## Structure

```text
user_data/                  Freqtrade user data folder
alphapilot/core/            proposal, workflow, lock, handbook skeletons
alphapilot/risk/            risk gate and position sizing skeletons
alphapilot/audit/           JSONL audit ledger skeleton
alphapilot/reports/         report schema and mock export
alphapilot/universe/        fixed Top 30 OKX USDT swap universe
scripts/                    safe PowerShell command wrappers
docs/                       V13.2/V13.3 docs and safety notes
```

## Setup

Install Docker Desktop before running Freqtrade commands.

Check local skeleton status:

```powershell
python -m alphapilot.scripts.print_project_status
python -m alphapilot.scripts.validate_config
```

Compile Python skeleton:

```powershell
python -m compileall alphapilot
```

## Freqtrade Commands

The scripts print commands by default. Use `-Run` only when you intentionally want to execute them.

Download public market data:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1
```

Run a local backtest command template:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_backtest.ps1
```

Export a mock AlphaPilot report:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/export_report.ps1
```

Safety scan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_safety.ps1
```

## V13.3 Volume Rebound V0.1

V13.3 implements the first AlphaPilot research strategy for baseline backtesting:

```text
AlphaPilot Volume Rebound V0.1
```

中文说明：

```text
V13.3 实现第一条 AlphaPilot 自研策略：放量反弹 V0.1。
本版本只用于研究和回测，不进行实盘交易，不接真实 API Key，不创建真实订单。
```

It does not trade live. It does not use real API keys. It is intended for research and backtesting only.

Core V0.1 rules:

- market: OKX USDT swap
- direction: long only
- timeframe: 15m
- fixed universe: Top 30 USDT swap pairs
- fixed stop loss: -3%
- take profit: +3%
- leverage: 5x research cap
- risk per trade: 1% documented research assumption
- fee rate: 0.05% one-way
- slippage rate: 0.05% one-way planned in reports, not yet applied by the Freqtrade command
- BTC crash filter: block new signals when BTC drops at least 1% over the latest three 15m candles
- 4h trend filter: current pair 4h close must be at least `EMA200 * 0.98`

Entry requires RSI14 between 30 and 55, volumeRatio at least 1.5, MACD histogram improvement, price near EMA20, and no chase above the Bollinger middle zone.

Backtest command preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_backtest.ps1 -Smoke -Timerange "20240101-20240701"
```

Download command preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" -Timeframes "15m,1h,4h" -Timerange "20240101-"
```

Add `-Run` only when Docker and Freqtrade are ready.

Report export:

```powershell
python -m alphapilot.reports.export_backtest_report
```

The exporter marks sample reports with `isMock=true`. It marks converted Freqtrade results with `isMock=false`.

The V13.3 strategy is not a live recommendation and not a production trading strategy.

## V13.4 Real Freqtrade Smoke Backtest

V13.4 completed the first real Freqtrade smoke backtest flow:

```text
public historical data download -> Freqtrade backtest -> Freqtrade JSON -> AlphaPilot report
```

The V13.4 smoke run used public OKX historical futures data only:

```text
Pairs: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
Timerange: 20260401-
Trades: 230
Win rate: 41.3043%
Total return: -15.542%
Max drawdown: 24.4939%
Profit factor: 0.8107
```

The versioned report is:

```text
reports/v13_4_smoke_backtest_report.json
```

It is a real converted Freqtrade result and contains:

```json
{
  "isMock": false
}
```

Runtime compatibility fixed in V13.4:

- `scripts/download_data.ps1` supports `-UseTop30`.
- `scripts/run_backtest.ps1` supports `-UseTop30`.
- Freqtrade 2026.6 config requires `entry_pricing` and `exit_pricing`; both are present in the backtest config and dry-run template.
- The report exporter supports the newer Freqtrade result layout where `.last_result.json` points to a zip file containing the real result JSON.
- Report export preserves missing real metrics as `null` and records `reportWarnings`.
- Real dynamic reports write `reports/latest_backtest_report.json` and `reports/smoke_backtest_report.json`; these are ignored so reruns do not pollute git status.
- Mock reports remain explicitly marked with `isMock=true`.

V13.4 is a process success, not a strategy approval. The current AlphaPilot Volume Rebound V0.1 smoke result is negative, with `profitFactor < 1`, negative total return, and high drawdown. It must not enter Dry-run. The next step is V13.4.1 Backtest Result Diagnosis.

## V13.4.1 Backtest Result Diagnosis

V13.4.1 diagnoses the first real smoke backtest result. It does not tune
strategy parameters, does not modify `AlphaPilotVolumeReboundV01.py`, and does
not enter Dry-run.

Run diagnosis:

```powershell
python -m alphapilot.reports.diagnose_backtest_result
```

Diagnosis outputs:

```text
reports/v13_4_1_diagnosis_report.json
reports/v13_4_1_diagnosis_summary.md
docs/V13.4.1-backtest-result-diagnosis.md
docs/v13_4_1_diagnosis_findings.md
```

Main findings from V13.4.1:

- The strategy cannot enter Dry-run.
- SOL contributed the largest pair-level loss: `-94.83085485 USDT`.
- April 2026 contributed the largest time-period loss: `-158.49408035 USDT`.
- `stop_loss` was the largest exit-reason loss: `-420.36251129 USDT`.
- `macd_histogram_two_candle_weakness` also lost heavily: `-345.28583144 USDT`.
- The weakest holding bucket was `1-3h`: `-120.76496941 USDT`.
- Fees were applied by Freqtrade and are material; slippage was not applied by the V13.4 command.
- Filter effectiveness is unavailable because V13.4 did not include skipped-signal instrumentation.

V13.4.1 prepares V0.2 candidate ideas, but those ideas are evidence categories,
not parameter changes. The next work should add signal audit instrumentation and
review the V0.2 candidates before any strategy modification.

## V13.4.2 Signal Audit Instrumentation

V13.4.2 adds skipped-signal audit instrumentation and filter effectiveness
tracking for AlphaPilot Volume Rebound V0.1.

This version does not tune strategy parameters, does not enter Dry-run, does not
call exchange private APIs, and does not create orders.

Run the audit:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_signal_audit.ps1
```

Outputs:

```text
reports/v13_4_2_signal_audit_report.json
reports/v13_4_2_signal_audit_summary.md
docs/V13.4.2-signal-audit-instrumentation.md
docs/filter-effectiveness-methodology.md
```

Current V13.4.2 smoke audit:

```text
Candles evaluated: 26496
Base candidate count: 26496
Final entry count: 305
Actual trade count: 230
Filter effectiveness available: true
Top skip reason: weak_4h_trend
Data missing count: 0
```

The largest primary blocks in the smoke sample are 4h trend, RSI, and volume
ratio. The least primary-blocking filter is the no-chase filter. These findings
prepare V13.4.3 strategy V0.2 candidate design, but V13.4.2 does not change the
V0.1 thresholds.

## V13.4.3 Strategy V0.2 Candidate Design

V13.4.3 creates evidence-based V0.2 strategy candidates from the V13.4.1
diagnosis and V13.4.2 signal audit. It does not tune parameters, does not run
Dry-run, does not change the V0.1 strategy, and prepares V13.4.4 comparative
backtesting.

V13.4.3 基于 V13.4.1 亏损诊断和 V13.4.2 信号审计，提出 V0.2 候选修改方向。本版本不调参、不进入
Dry-run、不修改 V0.1 真实策略，只为 V13.4.4 对比回测做准备。

Run candidate matrix generation:

```powershell
python -m alphapilot.reports.generate_v02_candidate_matrix
```

Outputs:

```text
reports/v13_4_3_v02_candidate_matrix.json
reports/v13_4_3_v02_candidate_summary.md
docs/V13.4.3-strategy-v02-candidate-design.md
docs/volume-rebound-v02-candidate-plan.md
```

V13.4.3 candidates:

```text
V0.2A Trend Strict Filter
V0.2B Volume Quality Filter
V0.2C Exit Cleanup
V0.2D Early Failure Exit
V0.2E Pair Risk Watchlist
```

All candidates are `candidate_only`. None are approved for Dry-run or live
trading.

Smoke preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" -Timeframes "15m,1h,4h" -Timerange "20260401-"
powershell -ExecutionPolicy Bypass -File scripts/run_backtest.ps1 -Timerange "20260401-" -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT"
```

Add `-Run` only after Docker Desktop is installed and running.

## Next Versions

- V13.4.3: use signal audit evidence to design V0.2 candidates without entering Dry-run.
- V13.5: run wider Top 30 historical tests only after diagnosis and risk gates are clearer.
- V13.6: connect mobile control-panel read-only views to exported research reports.
- V13.7+: consider dry-run architecture only after risk gates and audit rules are stronger.
