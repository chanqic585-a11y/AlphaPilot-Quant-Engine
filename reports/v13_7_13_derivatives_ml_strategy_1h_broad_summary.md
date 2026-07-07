# V13.5 Derivatives ML-Gated Strategy Report

This report is research-only. It does not approve live trading, does not use API keys, and does not create orders.

## Decision

- Shadow approved: `False`
- Paper approved: `False`
- Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `no_candidate_passed_55pct_winrate_2r_hard_gate`

## Best Candidate

- Trade count: `1009`
- Win rate: `43.6075`
- Reward/risk: `0.9731`
- Profit factor: `0.7525`
- Total return: `-87.3082`
- Max drawdown: `88.8058`
- Research worth continuing: `False`

## Best Deterministic Mined Candidate

- Columns: `bucket_bollinger_z, bucket_mark_basis_pct, bucket_btc_return_3`
- Values: `> 2.0, (-0.0002, 0.0002], > 0.06`
- Trade count: `89`
- Win rate: `62.9213`
- Reward/risk: `1.6618`
- Profit factor: `2.8201`
- Max drawdown: `20.2483`
- Hard gate passed: `False`
- Fail reasons: `trade_count_below_100, reward_risk_below_1_8, max_drawdown_above_20, recent_2026_profit_factor_below_1`

## Data

- Panel rows: `798276`
- Loaded pairs: `AAVE/USDT:USDT, ADA/USDT:USDT, APT/USDT:USDT, ARB/USDT:USDT, ATOM/USDT:USDT, AVAX/USDT:USDT, BCH/USDT:USDT, BTC/USDT:USDT, DOGE/USDT:USDT, DOT/USDT:USDT, ETC/USDT:USDT, ETH/USDT:USDT, FIL/USDT:USDT, INJ/USDT:USDT, LINK/USDT:USDT, LTC/USDT:USDT, NEAR/USDT:USDT, OP/USDT:USDT, ORDI/USDT:USDT, PEPE/USDT:USDT, SEI/USDT:USDT, SOL/USDT:USDT, SUI/USDT:USDT, TIA/USDT:USDT, TRX/USDT:USDT, UNI/USDT:USDT, WIF/USDT:USDT, XRP/USDT:USDT`
- Missing pairs: `none`
- Open interest status: `unavailable_not_fabricated`

## Recommendations

- No V13.5 candidate cleared the 55% win-rate and 2R hard gate.
- Do not start paper or Dry-run from this result.
- Prioritize richer derivatives data: open interest, liquidation proxies, order-book/liquidity spread, and longer funding history.
- Best observed gated metrics: trades=1009, winRate=43.6075, rewardRisk=0.9731, profitFactor=0.7525. Best deterministic mined candidate: trades=89, winRate=62.9213, rewardRisk=1.6618, profitFactor=2.8201, failReasons=['trade_count_below_100', 'reward_risk_below_1_8', 'max_drawdown_above_20', 'recent_2026_profit_factor_below_1'].
