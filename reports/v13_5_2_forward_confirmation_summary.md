# V13.5.2 Forward Confirmation and Local Paper Sandbox Report

This report is research-only. Local paper sandbox means local simulated observation only.
It does not approve exchange Dry-run, API keys, account reads, orders, or live trading.

## Decision

- Local paper sandbox approved: `True`
- Local paper candidate IDs: `v13_5_1_1h_short_reversal_bull_relative_return`
- Exchange Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `local_paper_sandbox_candidate_confirmed`

## Best Candidate

- Candidate ID: `v13_5_1_1h_short_reversal_bull_relative_return`
- Timeframe: `1h`
- Columns: `bucket_setupName, bucket_btc_regime, bucket_relative_return_6`
- Values: `short_reversal_candidate, bull, (-0.01, 0.01]`
- Confirmation trades: `57`
- Confirmation win rate: `70.1754`
- Confirmation reward/risk: `2.0235`
- Confirmation profit factor: `4.7612`
- Confirmation total return: `346.661`
- Confirmation max drawdown: `11.9756`
- Local paper sandbox fail reasons: ``

## Candidate Confirmations

### v13_5_1_1h_short_reversal_bull_relative_return

- Approved: `True`
- Trades: `57`
- Win rate: `70.1754`
- Reward/risk: `2.0235`
- Profit factor: `4.7612`
- Max drawdown: `11.9756`
- Fail reasons: `none`

### v13_5_1_4h_bear_regime_bollinger_reversal

- Approved: `False`
- Trades: `50`
- Win rate: `56.0`
- Reward/risk: `1.9965`
- Profit factor: `2.5411`
- Max drawdown: `35.4801`
- Fail reasons: `confirmation_drawdown_above_20`

## Next Step

- Start local paper sandbox logging for the approved candidate only. Keep exchange Dry-run disabled.

## Safety Boundary

- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No real orders.
- No automatic trading.
- Exchange Dry-run remains disabled.
