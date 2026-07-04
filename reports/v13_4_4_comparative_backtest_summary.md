# V13.4.4 Comparative Backtest Summary

## Decision

- Dry-run approved: False
- Best candidate: AlphaPilotVolumeReboundV02CExitCleanup
- Slippage applied: False

## Comparison Table

| Strategy | Return % | Drawdown % | Profit Factor | Trades | Win Rate % | Max Loss Streak | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| AlphaPilotVolumeReboundV01 | -15.542 | 24.4939 | 0.8107 | 230 | 41.3043 | 13 | False |
| AlphaPilotVolumeReboundV02ATrendStrict | -11.6607 | 21.0664 | 0.8251 | 179 | 41.3408 | 10 | True |
| AlphaPilotVolumeReboundV02BVolumeQuality | -4.0845 | 11.4841 | 0.9104 | 116 | 45.6897 | 9 | True |
| AlphaPilotVolumeReboundV02CExitCleanup | -6.1609 | 17.8594 | 0.9319 | 220 | 51.3636 | 10 | True |
| AlphaPilotVolumeReboundV02DEarlyFailureExit | -15.6258 | 24.3002 | 0.7979 | 231 | 36.7965 | 13 | False |
| AlphaPilotVolumeReboundV02EPairRiskWatchlist | -10.3361 | 17.93 | 0.8406 | 182 | 40.6593 | 10 | True |

## Candidate Details

### AlphaPilotVolumeReboundV02ATrendStrict

- Candidate ID: alpha_volume_rebound_v02_a_trend_strict
- Executable: True
- Backtest report: user_data/backtest_results/v13_4_4_AlphaPilotVolumeReboundV02ATrendStrict.zip
- Passed comparison gate: True
- Total return: -11.6607
- Max drawdown: 21.0664
- Profit factor: 0.8251
- Trade count: 179
- Stop-loss loss: -335.58167292
- MACD weakness exit loss: -286.84500658

### AlphaPilotVolumeReboundV02BVolumeQuality

- Candidate ID: alpha_volume_rebound_v02_b_volume_quality
- Executable: True
- Backtest report: user_data/backtest_results/v13_4_4_AlphaPilotVolumeReboundV02BVolumeQuality.zip
- Passed comparison gate: True
- Total return: -4.0845
- Max drawdown: 11.4841
- Profit factor: 0.9104
- Trade count: 116
- Stop-loss loss: -295.95327658
- MACD weakness exit loss: -131.3940828

### AlphaPilotVolumeReboundV02CExitCleanup

- Candidate ID: alpha_volume_rebound_v02_c_exit_cleanup
- Executable: True
- Backtest report: user_data/backtest_results/v13_4_4_AlphaPilotVolumeReboundV02CExitCleanup.zip
- Passed comparison gate: True
- Total return: -6.1609
- Max drawdown: 17.8594
- Profit factor: 0.9319
- Trade count: 220
- Stop-loss loss: -779.47102126
- MACD weakness exit loss: None

### AlphaPilotVolumeReboundV02DEarlyFailureExit

- Candidate ID: alpha_volume_rebound_v02_d_early_failure_exit
- Executable: True
- Backtest report: user_data/backtest_results/v13_4_4_AlphaPilotVolumeReboundV02DEarlyFailureExit.zip
- Passed comparison gate: False
- Total return: -15.6258
- Max drawdown: 24.3002
- Profit factor: 0.7979
- Trade count: 231
- Stop-loss loss: -396.34712289
- MACD weakness exit loss: -290.96446658

### AlphaPilotVolumeReboundV02EPairRiskWatchlist

- Candidate ID: alpha_volume_rebound_v02_e_pair_risk_watchlist
- Executable: True
- Backtest report: user_data/backtest_results/v13_4_4_AlphaPilotVolumeReboundV02EPairRiskWatchlist.zip
- Passed comparison gate: True
- Total return: -10.3361
- Max drawdown: 17.93
- Profit factor: 0.8406
- Trade count: 182
- Stop-loss loss: -278.32662503
- MACD weakness exit loss: -317.91744313

## Reasons

- V13.4.4 is comparative backtesting only.
- Dry-run remains blocked until longer-range and broader-pair validation exists.
- Slippage is not applied by the Freqtrade command; results are not live-performance estimates.
- AlphaPilotVolumeReboundV02CExitCleanup passed the first comparison gate but still requires more validation.

## Warnings

- AlphaPilotVolumeReboundV01: profit_total_pct missing; normalized profit_total instead.
- AlphaPilotVolumeReboundV02ATrendStrict: profit_total_pct missing; normalized profit_total instead.
- AlphaPilotVolumeReboundV02BVolumeQuality: profit_total_pct missing; normalized profit_total instead.
- AlphaPilotVolumeReboundV02CExitCleanup: profit_total_pct missing; normalized profit_total instead.
- AlphaPilotVolumeReboundV02DEarlyFailureExit: profit_total_pct missing; normalized profit_total instead.
- AlphaPilotVolumeReboundV02EPairRiskWatchlist: profit_total_pct missing; normalized profit_total instead.

## Safety

V13.4.4 runs local Freqtrade backtesting only. It does not enter Dry-run, approve live trading, use API keys, call Trade API or Withdraw API, read accounts, create orders, or auto trade.
