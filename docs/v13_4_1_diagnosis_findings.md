# V13.4.1 Diagnosis Findings

## Baseline

Source report:

```text
reports/v13_4_smoke_backtest_report.json
```

Diagnosis outputs:

```text
reports/v13_4_1_diagnosis_report.json
reports/v13_4_1_diagnosis_summary.md
```

The source report is real:

```text
isMock=false
```

## Overall Metrics

| Metric | Value |
| --- | ---: |
| Total trades | 230 |
| Winning trades | 95 |
| Losing trades | 135 |
| Win rate | 41.3043% |
| Total return | -15.542% |
| Max drawdown | 24.4939% |
| Profit factor | 0.8107 |
| Average profit | -0.2092% |
| Average win | 7.00837262 USDT |
| Average loss | -6.08307887 USDT |
| Expectancy | -0.67574021 |
| Max consecutive losses | 13 |
| Average holding time | 68 minutes |
| Median holding time | 60 minutes |

Conclusion: V13.4 flow passed, but the strategy result is negative and cannot
enter Dry-run.

## Pair Breakdown

| Pair | Trades | Win rate | Net profit | Net profit % | Profit factor | Max consecutive losses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC/USDT:USDT | 72 | 36.1111% | -28.14238613 | -2.81% | 0.8541 | 8 |
| ETH/USDT:USDT | 59 | 40.678% | -32.44700789 | -3.24% | 0.8564 | 4 |
| SOL/USDT:USDT | 99 | 45.4545% | -94.83085485 | -9.48% | 0.7643 | 8 |

Largest pair-level drag: `SOL/USDT:USDT`.

Best relative pair: `BTC/USDT:USDT`, but it was still negative.

## Monthly Breakdown

| Period | Trades | Net profit | Profit factor |
| --- | ---: | ---: | ---: |
| 30/04/2026 | 118 | -158.49408035 | 0.6889 |
| 31/05/2026 | 94 | -35.74506306 | 0.8637 |
| 30/06/2026 | 10 | 1.11691949 | 1.0292 |
| 31/07/2026 | 8 | 37.70197505 | 4.3388 |

Largest time-period drag: April 2026. The smoke sample improved later, but this
is not enough to approve Dry-run.

## Exit Reason Breakdown

| Exit reason | Trades | Net profit | Win rate | Avg win | Avg loss | Profit factor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| roi | 70 | 621.39988306 | 100.0% | 8.87714119 | unavailable | 0.0 |
| time_stop_12_candles_no_profit | 3 | -11.1717892 | 0.0% | unavailable | -3.72392973 | 0.0 |
| macd_histogram_two_candle_weakness | 117 | -345.28583144 | 21.3675% | 1.77582064 | -4.23566682 | 0.1139 |
| stop_loss | 40 | -420.36251129 | 0.0% | unavailable | -10.50906278 | 0.0 |

Main observation: ROI exits were profitable, but stop loss and MACD weakness
exits more than offset those gains.

## Holding Time Breakdown

| Bucket | Trades | Win rate | Net profit |
| --- | ---: | ---: | ---: |
| 0-1h | 102 | 44.1176% | -42.92963304 |
| 1-3h | 117 | 36.7521% | -120.76496941 |
| 3-6h | 11 | 63.6364% | 8.27435358 |
| 6-12h | 0 | unavailable | 0.0 |
| 12h+ | 0 | unavailable | 0.0 |

The weakest holding bucket was 1-3h.

## Cost Analysis

| Item | Value |
| --- | ---: |
| Fees available | true |
| Fees applied by Freqtrade | true |
| Estimated fees from orders | 339.82529451 USDT |
| Fees / gross profit | 0.5104 |
| Fees / absolute PnL | 0.2285 |
| Slippage applied | false |
| Slippage available | false |
| Total volume | 679650.58902678 USDT |

Fees are material for this 15m sample. Slippage was not applied by the V13.4
Freqtrade command, so V13.4.1 cannot treat slippage-adjusted performance as
known.

## Consecutive Loss Analysis

| Item | Value |
| --- | --- |
| Max consecutive losses | 13 |
| Symbols in worst count streak | BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT |

Loss streak risk is significant. A future strategy version should consider
pause logic only after signal audit data exists.

## Filter Effectiveness

Filter effectiveness is unavailable in V13.4 because skipped-signal
instrumentation was not present.

Reviewed filters:

- BTC crash filter
- 4h trend filter
- RSI 30-55 filter
- volumeRatio >= 1.5
- MACD histogram improving
- close >= EMA20 * 0.995
- pullback / no chase filter

Recommended instrumentation:

- pre-filter signal count
- post-filter signal count
- skip reason count
- per-pair skip reason count

## V0.2 Candidate Ideas

| Classification | Candidate |
| --- | --- |
| needs_more_backtest | Diagnose and possibly strengthen the 4h trend filter. |
| hypothesis_only | Evaluate a higher volumeRatio threshold or a scored volume confirmation. |
| needs_more_backtest | Add a stronger no-chase filter after sharp candles. |
| data_supported | Review MACD weakness exit timing against actual loss distribution. |
| data_supported | Analyze whether -3% stoploss and +3% ROI produce poor payoff at current win rate. |
| data_supported | Add signal audit instrumentation before parameter tuning. |

## Do Not Change Yet

- Do not modify stoploss yet.
- Do not modify take profit yet.
- Do not modify RSI range yet.
- Do not modify volumeRatio threshold yet.
- Do not modify BTC crash filter yet.
- Do not enter Dry-run.
- Do not expand to Top30 full backtest before diagnosis is reviewed.

## Final V13.4.1 Position

V13.4.1 explains why the V13.4 smoke backtest is not acceptable for Dry-run. It
does not optimize the strategy and does not approve real or simulated execution.
