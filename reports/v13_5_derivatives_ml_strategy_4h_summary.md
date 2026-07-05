# V13.5 Derivatives ML-Gated Strategy Report

This report is research-only. It does not approve live trading, does not use API keys, and does not create orders.

## Decision

- Shadow approved: `False`
- Paper approved: `False`
- Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `no_candidate_passed_55pct_winrate_2r_hard_gate`

## Best Candidate

- Trade count: `28`
- Win rate: `53.5714`
- Reward/risk: `1.6189`
- Profit factor: `1.868`
- Total return: `44.7955`
- Max drawdown: `17.7164`
- Research worth continuing: `False`

## Best Deterministic Mined Candidate

- Columns: `bucket_setupName, bucket_pair, bucket_mark_basis_pct`
- Values: `long_continuation_candidate, ETH/USDT:USDT, (-0.0002, 0.0002]`
- Trade count: `94`
- Win rate: `61.7021`
- Reward/risk: `1.5668`
- Profit factor: `2.5243`
- Max drawdown: `26.0341`
- Hard gate passed: `False`
- Fail reasons: `trade_count_below_100, reward_risk_below_1_8, max_drawdown_above_20`

## Data

- Panel rows: `16485`
- Loaded pairs: `BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT`
- Missing pairs: `none`
- Open interest status: `unavailable_not_fabricated`

## Recommendations

- No V13.5 candidate cleared the 55% win-rate and 2R hard gate.
- Do not start paper or Dry-run from this result.
- Prioritize richer derivatives data: open interest, liquidation proxies, order-book/liquidity spread, and longer funding history.
- Best observed gated metrics: trades=28, winRate=53.5714, rewardRisk=1.6189, profitFactor=1.868. Best deterministic mined candidate: trades=94, winRate=61.7021, rewardRisk=1.5668, profitFactor=2.5243, failReasons=['trade_count_below_100', 'reward_risk_below_1_8', 'max_drawdown_above_20'].
