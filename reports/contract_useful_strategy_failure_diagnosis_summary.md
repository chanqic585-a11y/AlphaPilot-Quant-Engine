# External 5m Failure Diagnosis

- Status: `completed`
- Source progress: `100.0000%`
- Strategy count: `6`
- All strategies rejected: `True`
- Raw pocket count: `0`

Safety boundary: local research report only. No Dry-run, no live trading, no private API, no account read, no order creation.

## Verdict

Do not promote any full-market 5m strategy. The batch shows severe cost, overtrading, and drawdown failure.

## Failure Flags

- `drawdown_above_50pct`: `6`
- `negative_slippage_adjusted_return`: `6`
- `raw_pf_below_1`: `6`
- `slippage_adjusted_pf_below_1`: `6`
- `win_rate_below_45pct`: `6`
- `reward_risk_below_2`: `4`

## Top Raw Pair Pockets

| Rank | Tier | Strategy | Pair | Score | Trades | Raw Return | Raw PF | Raw Win Rate |
|---:|---|---|---|---:|---:|---:|---:|---:|
| 0 | none | -- | -- | -- | -- | -- | -- | -- |

## Recommended Next Actions

- Keep the current full-market 5m strategy batch out of sandbox promotion.
- Retest only raw pocket pairs with explicit pair whitelist, higher selectivity, and lower trade frequency.
- Add regime/liquidity filters before re-running 5m candidates.
- Stress test raw pockets with 5bp and 10bp extra one-way slippage before any forward observation.
- Prefer fewer trades with clearer 2R structure over high-frequency overtrading.
