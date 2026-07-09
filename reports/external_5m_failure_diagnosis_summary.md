# External 5m Failure Diagnosis

- Status: `completed`
- Source progress: `100.0000%`
- Strategy count: `23`
- All strategies rejected: `True`
- Raw pocket count: `38`

Safety boundary: local research report only. No Dry-run, no live trading, no private API, no account read, no order creation.

## Verdict

Do not promote any full-market 5m strategy. The batch shows severe cost, overtrading, and drawdown failure.

## Failure Flags

- `negative_slippage_adjusted_return`: `23`
- `raw_pf_below_1`: `23`
- `slippage_adjusted_pf_below_1`: `23`
- `win_rate_below_45pct`: `23`
- `drawdown_above_50pct`: `22`
- `reward_risk_below_2`: `20`
- `sample_too_small`: `1`

## Top Raw Pair Pockets

| Rank | Tier | Strategy | Pair | Score | Trades | Raw Return | Raw PF | Raw Win Rate |
|---:|---|---|---|---:|---:|---:|---:|---:|
| 1 | raw_pocket_retest_candidate | 4H EMA趋势做空 | GAS/USDT:USDT | 85.1900 | 1449 | 14.3514% | 1.4171 | 32.7812% |
| 2 | raw_pocket_retest_candidate | 低频4H方向策略 | ZRX/USDT:USDT | 75.6400 | 5463 | 18.6984% | 1.1240 | 47.5197% |
| 3 | raw_pocket_retest_candidate | BenchmarkRSIMeanReversion | DOGE/USDT:USDT | 74.1400 | 1817 | 2.0129% | 1.3177 | 42.7628% |
| 4 | raw_pocket_retest_candidate | 4H 波动压缩突破 | CRO/USDT:USDT | 50.1700 | 510 | 1.0460% | 1.1907 | 30.3922% |
| 5 | raw_pocket_retest_candidate | 4H 跌破反抽做空 | GAS/USDT:USDT | 50.0400 | 778 | 1.2155% | 1.1487 | 34.3188% |
| 6 | raw_pocket_retest_candidate | 4H EMA趋势做空 | ICX/USDT:USDT | 49.3900 | 1294 | 1.2853% | 1.1239 | 36.0124% |
| 7 | raw_pocket_reference_only | BenchmarkRSIMeanReversion | USDC/USDT:USDT | 72.8100 | 727 | 0.0904% | 1.5221 | 51.0316% |
| 8 | raw_pocket_reference_only | 4H 布林均值回归做空 | USDC/USDT:USDT | 66.1300 | 287 | 0.3560% | 1.6831 | 68.2927% |
| 9 | raw_pocket_reference_only | 4H 布林均值回归做多 | USDC/USDT:USDT | 63.6300 | 257 | 0.1562% | 1.5620 | 73.9300% |
| 10 | raw_pocket_reference_only | 4H 跌破反抽做空 | LPT/USDT:USDT | 52.9200 | 595 | 0.0212% | 1.2497 | 34.6218% |
| 11 | raw_pocket_reference_only | 4H 跌破反抽做空 | ZRX/USDT:USDT | 51.7900 | 1807 | 3.1923% | 1.0703 | 32.2081% |
| 12 | raw_pocket_reference_only | 4H 跌破反抽做空 | SOL/USDT:USDT | 48.0100 | 1032 | 0.1384% | 1.2219 | 29.9419% |
| 13 | raw_pocket_reference_only | 4H 波动压缩突破 | SOL/USDT:USDT | 46.9500 | 756 | 0.9304% | 1.1740 | 28.5714% |
| 14 | raw_pocket_reference_only | 4H 布林均值回归做多 | EGLD/USDT:USDT | 45.4700 | 167 | 0.0162% | 1.2121 | 53.2934% |
| 15 | raw_pocket_reference_only | 4H EMA趋势做空 | ZRX/USDT:USDT | 45.4500 | 1630 | 2.1106% | 1.0475 | 33.7423% |
| 16 | raw_pocket_reference_only | 4H 跌破反抽做空 | ICX/USDT:USDT | 45.1500 | 1113 | 0.9575% | 1.0970 | 35.5795% |
| 17 | raw_pocket_reference_only | 4H 布林均值回归做空 | AUCTION/USDT:USDT | 43.1600 | 1300 | 0.0049% | 1.0800 | 41.9231% |
| 18 | raw_pocket_reference_only | 4H 布林均值回归做多 | TURBO/USDT:USDT | 42.9100 | 384 | 0.0005% | 1.1166 | 45.5729% |
| 19 | raw_pocket_reference_only | BenchmarkRSIMeanReversion | GAS/USDT:USDT | 42.1600 | 913 | 0.4574% | 1.0732 | 37.8970% |
| 20 | raw_pocket_reference_only | 4H EMA趋势做空 | MANA/USDT:USDT | 41.2000 | 1246 | 0.9829% | 1.0876 | 30.6581% |

## Recommended Next Actions

- Keep the current full-market 5m strategy batch out of sandbox promotion.
- Retest only raw pocket pairs with explicit pair whitelist, higher selectivity, and lower trade frequency.
- Add regime/liquidity filters before re-running 5m candidates.
- Stress test raw pockets with 5bp and 10bp extra one-way slippage before any forward observation.
- Prefer fewer trades with clearer 2R structure over high-frequency overtrading.
