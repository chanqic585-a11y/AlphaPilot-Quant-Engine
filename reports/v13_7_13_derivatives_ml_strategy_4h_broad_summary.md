# V13.5 Derivatives ML-Gated Strategy Report

This report is research-only. It does not approve live trading, does not use API keys, and does not create orders.

## Decision

- Shadow approved: `False`
- Paper approved: `False`
- Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `no_candidate_passed_55pct_winrate_2r_hard_gate`

## Best Candidate

- Trade count: `41`
- Win rate: `26.8293`
- Reward/risk: `1.2551`
- Profit factor: `0.4602`
- Total return: `-36.5201`
- Max drawdown: `36.5852`
- Research worth continuing: `False`

## Best Deterministic Mined Candidate

- Columns: `bucket_pair, bucket_rsi14, bucket_return_3`
- Values: `TRX/USDT:USDT, (40, 50], (0.0, 0.015]`
- Trade count: `86`
- Win rate: `68.6047`
- Reward/risk: `1.5801`
- Profit factor: `3.4529`
- Max drawdown: `12.1828`
- Hard gate passed: `False`
- Fail reasons: `trade_count_below_100, reward_risk_below_1_8, recent_2026_profit_factor_below_1`

## Data

- Panel rows: `359791`
- Loaded pairs: `AAVE/USDT:USDT, ADA/USDT:USDT, APT/USDT:USDT, ARB/USDT:USDT, ATOM/USDT:USDT, AVAX/USDT:USDT, BCH/USDT:USDT, BNB/USDT:USDT, BTC/USDT:USDT, CFX/USDT:USDT, CRV/USDT:USDT, DOGE/USDT:USDT, DOT/USDT:USDT, DYDX/USDT:USDT, ETC/USDT:USDT, ETH/USDT:USDT, FIL/USDT:USDT, FLOW/USDT:USDT, GRT/USDT:USDT, INJ/USDT:USDT, KSM/USDT:USDT, LINK/USDT:USDT, LTC/USDT:USDT, NEAR/USDT:USDT, OP/USDT:USDT, ORDI/USDT:USDT, PEPE/USDT:USDT, SEI/USDT:USDT, SHIB/USDT:USDT, SOL/USDT:USDT, SUI/USDT:USDT, TIA/USDT:USDT, TRX/USDT:USDT, UNI/USDT:USDT, WIF/USDT:USDT, XRP/USDT:USDT, ZK/USDT:USDT, ZRO/USDT:USDT`
- Missing pairs: `none`
- Open interest status: `unavailable_not_fabricated`

## Recommendations

- No V13.5 candidate cleared the 55% win-rate and 2R hard gate.
- Do not start paper or Dry-run from this result.
- Prioritize richer derivatives data: open interest, liquidation proxies, order-book/liquidity spread, and longer funding history.
- Best observed gated metrics: trades=41, winRate=26.8293, rewardRisk=1.2551, profitFactor=0.4602. Best deterministic mined candidate: trades=86, winRate=68.6047, rewardRisk=1.5801, profitFactor=3.4529, failReasons=['trade_count_below_100', 'reward_risk_below_1_8', 'recent_2026_profit_factor_below_1'].
