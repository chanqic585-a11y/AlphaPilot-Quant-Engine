# V13.4.5 Expanded Validation Summary

## Decision

- Dry-run approved: False
- Best raw candidate: AlphaPilotVolumeReboundV02CExitCleanup
- Best slippage-adjusted candidate: AlphaPilotVolumeReboundV02CExitCleanup
- Slippage by Freqtrade: False
- Slippage by post-processing: True

## Scope

- Pairs mode: fixed_top30
- Timerange: 20260101-
- Timeframe: 15m
- One-way slippage rate: 0.0005

## Raw Comparison

| Strategy | Return % | Drawdown % | Profit Factor | Trades | Win Rate % | Max Loss Streak |
|---|---:|---:|---:|---:|---:|---:|
| AlphaPilotVolumeReboundV01 | -99.2732 | 99.3724 | 0.6689 | 2701 | 37.2825 | 28 |
| AlphaPilotVolumeReboundV02BVolumeQuality | -94.171 | 94.7185 | 0.6152 | 1515 | 36.9637 | 19 |
| AlphaPilotVolumeReboundV02CExitCleanup | -99.1303 | 99.2719 | 0.6739 | 2496 | 43.4295 | 25 |
| AlphaPilotVolumeReboundV02EPairRiskWatchlist | -99.3093 | 99.3953 | 0.6637 | 2671 | 37.0273 | 20 |

## Slippage-Adjusted Comparison

| Strategy | Adj Return % | Adj Drawdown % | Adj PF | Trades | Adj Win Rate % | Max Loss Streak | Slippage Cost | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| AlphaPilotVolumeReboundV01 | -193.4577 | 191.6168 | 0.4603 | 2701 | 34.6909 | 28 | 941.84466739 | False |
| AlphaPilotVolumeReboundV02BVolumeQuality | -168.5489 | 165.9553 | 0.4225 | 1515 | 34.7195 | 36 | 743.77896729 | False |
| AlphaPilotVolumeReboundV02CExitCleanup | -187.2377 | 182.3083 | 0.4726 | 2496 | 39.7436 | 25 | 881.07407065 | True |
| AlphaPilotVolumeReboundV02EPairRiskWatchlist | -191.7425 | 190.0944 | 0.4569 | 2671 | 34.4066 | 20 | 924.33185017 | False |

## Supported Pairs

BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT, DOGE/USDT:USDT, XRP/USDT:USDT, ADA/USDT:USDT, AVAX/USDT:USDT, LINK/USDT:USDT, SUI/USDT:USDT, APT/USDT:USDT, OP/USDT:USDT, ARB/USDT:USDT, LTC/USDT:USDT, BCH/USDT:USDT, DOT/USDT:USDT, NEAR/USDT:USDT, PEPE/USDT:USDT, WIF/USDT:USDT, ORDI/USDT:USDT, INJ/USDT:USDT, FIL/USDT:USDT, ETC/USDT:USDT, TRX/USDT:USDT, UNI/USDT:USDT, AAVE/USDT:USDT, ATOM/USDT:USDT, SEI/USDT:USDT, TIA/USDT:USDT

## Excluded Pairs

- TON/USDT:USDT: not present in completed Freqtrade backtest result
- FET/USDT:USDT: not present in completed Freqtrade backtest result

## Reasons

- V13.4.5 is expanded validation and slippage post-processing only.
- Slippage is not applied by Freqtrade; it is applied by AlphaPilot report post-processing.
- Dry-run remains blocked regardless of expanded gate outcome.
- 1 candidate(s) passed the expanded research gate, but longer validation is still required.

## Warnings

- All candidates remain negative after slippage post-processing.
- Post-processed drawdown can exceed 100% because slippage is applied after Freqtrade without a liquidation model.
- Some requested pairs were excluded by exchange compatibility or missing completed result coverage.

## Safety

V13.4.5 uses local Freqtrade backtesting artifacts and public historical data only. It does not enter Dry-run, approve live trading, use API keys, call Trade API or Withdraw API, read accounts, create orders, or auto trade.
