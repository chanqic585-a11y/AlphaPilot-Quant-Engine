# AlphaPilot Quant Engine

AlphaPilot Quant Engine is the future backend research and execution-control layer for AlphaPilot.

Current version:

```text
AlphaPilot V13.2 - Quant Engine Skeleton With Freqtrade Foundation
```

## Positioning

V13.2 creates a backend skeleton for future research, backtesting, dry-run preparation, proposal review, risk gating, audit logging, and controlled execution design.

It is separate from the AlphaPilot Mobile App. The mobile app remains the phone-side AI control panel and manual trade record interface. This repository is the backend quant foundation.

## Safety Boundary

V13.2 does not perform live trading.

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

V13.2 only creates the foundation. Strategy quality, backtest execution, Freqtrade tuning, and live execution are later work.

## Structure

```text
user_data/                  Freqtrade user data folder
alphapilot/core/            proposal, workflow, lock, handbook skeletons
alphapilot/risk/            risk gate and position sizing skeletons
alphapilot/audit/           JSONL audit ledger skeleton
alphapilot/reports/         report schema and mock export
alphapilot/universe/        fixed Top 30 OKX USDT swap universe
scripts/                    safe PowerShell command wrappers
docs/                       V13.2 docs and safety notes
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

## V13.2 Strategy Placeholder

`AlphaPilotVolumeReboundV01` is a research/backtest strategy placeholder.

Consensus parameters recorded in this skeleton:

- strategyId: `alpha_volume_rebound_v01`
- market: OKX USDT swap
- direction: long only
- timeframe: 15m
- fixed stop loss: -3%
- take profit: +3%
- leverage: 5x configurable
- risk per trade: 1%
- fee rate: 0.05% one-way
- slippage rate: 0.05% one-way
- BTC crash filter: block new signals when BTC drops at least 1% over the latest three 15m candles
- universe: fixed Top 30

The V13.2 strategy is not a live recommendation and not a production trading strategy.

## Next Versions

- V13.3: implement and test Volume Rebound V0.1 backtest logic.
- V13.4: standardize Freqtrade result conversion into AlphaPilot report format.
- V13.5: connect mobile control-panel read-only views to exported research reports.
- V13.6+: consider dry-run architecture only after risk gates and audit rules are stronger.
