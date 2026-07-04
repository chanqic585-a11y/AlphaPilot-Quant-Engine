# AlphaPilot Quant Engine

AlphaPilot Quant Engine is the future backend research and execution-control layer for AlphaPilot.

Current version:

```text
AlphaPilot V13.3 - Volume Rebound V0.1 Strategy and Baseline Backtest
```

## Positioning

V13.3 builds on the backend skeleton and implements the first AlphaPilot research strategy for baseline backtesting.

It is separate from the AlphaPilot Mobile App. The mobile app remains the phone-side AI control panel and manual trade record interface. This repository is the backend quant foundation.

## Safety Boundary

V13.3 does not perform live trading.

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

V13.3 starts strategy backtesting work. Strategy quality, larger historical tests, Freqtrade tuning, and any controlled execution design remain later work.

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

## Next Versions

- V13.4: run wider Top 30 historical tests and improve skipped-signal aggregation.
- V13.5: connect mobile control-panel read-only views to exported research reports.
- V13.6+: consider dry-run architecture only after risk gates and audit rules are stronger.
