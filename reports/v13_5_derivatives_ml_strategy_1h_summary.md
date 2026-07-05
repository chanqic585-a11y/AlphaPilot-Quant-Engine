# V13.5 Derivatives ML-Gated Strategy Report

This report is research-only. It does not approve live trading, does not use API keys, and does not create orders.

## Decision

- Shadow approved: `False`
- Paper approved: `False`
- Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `no_candidate_passed_55pct_winrate_2r_hard_gate`

## Best Candidate

- Trade count: `271`
- Win rate: `51.6605`
- Reward/risk: `0.9928`
- Profit factor: `1.061`
- Total return: `7.0734`
- Max drawdown: `73.3918`
- Research worth continuing: `False`

## Best Deterministic Mined Candidate

- Columns: `bucket_setupName, bucket_pair, bucket_atr_pct`
- Values: `long_continuation_candidate, SOL/USDT:USDT, <= 0.01`
- Trade count: `106`
- Win rate: `57.5472`
- Reward/risk: `1.5581`
- Profit factor: `2.112`
- Max drawdown: `36.7233`
- Hard gate passed: `False`
- Fail reasons: `reward_risk_below_1_8, max_drawdown_above_20`

## Data

- Panel rows: `13308`
- Loaded pairs: `BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT`
- Missing pairs: `none`
- Open interest status: `unavailable_not_fabricated`

## Recommendations

- No V13.5 candidate cleared the 55% win-rate and 2R hard gate.
- Do not start paper or Dry-run from this result.
- Prioritize richer derivatives data: open interest, liquidation proxies, order-book/liquidity spread, and longer funding history.
- Best observed gated metrics: trades=271, winRate=51.6605, rewardRisk=0.9928, profitFactor=1.061. Best deterministic mined candidate: trades=106, winRate=57.5472, rewardRisk=1.5581, profitFactor=2.112, failReasons=['reward_risk_below_1_8', 'max_drawdown_above_20'].
