# V13.27.17 Formal Workflow Verification Summary

## Scope

- Registered executable event-window definitions: 7
- Completed original formal backtests: 6
- Checkpoint-paused original formal backtests: 1
- Bounded structural-redesign backtests completed: 4
- Passed formal backtests: 0
- Demo releases created: 0
- Live releases created: 0

## Original Results

| Timeframe | Strategy | Trades | PF | Average net R | Maximum drawdown R | Result |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 5m | 趋势回踩事件确认 学习版 ATR2.2 | 1296 | 0.79628024 | -0.15208090 | 201.50477509 | failed |
| 5m | 假突破反转环境确认 学习版 ATR2.2 | 581 | 0.88665121 | -0.08217782 | 97.25323853 | failed |
| 15m | 趋势回踩双趋势确认 因子后继 ATR1.2 | 909 | 0.89219645 | -0.07659869 | 71.42050965 | failed |
| 15m | 趋势回踩波动环境确认 因子后继 ATR1.2 | 390 | 0.84050962 | -0.11732317 | 46.99943080 | failed |
| 15m | 假突破弱趋势反转 因子后继 ATR1.2 | 626 | 1.00940092 | 0.00640423 | 66.09165227 | failed |
| 15m | 弱势回抽市场斜率确认 因子后继 ATR1.2 | 393 | 0.90229483 | -0.07329969 | 62.23142475 | failed |
| 1h | 深弱势扫低收回 因子后继 ATR1.2 | -- | -- | -- | -- | checkpoint-paused during official data preparation |

All six completed originals failed cost stress, maximum drawdown, and minimum
profit factor. Five also failed positive average net R. The bounded redesign
loop did not force a pass: four generated successors failed and the loop
stopped at its configured boundary.

## Interpretation

The candidate pre-screen successfully reduced the inventory but was not a
substitute for the formal all-market gate. The next generation should reduce
event frequency and cross-symbol loss concentration, then prove positive
cost-adjusted expectancy on development, temporal validation, and symbol
holdback before locked evidence is opened. The target remains at least `2R`.
