# V13.5.4 Local Paper Monitoring Report

This report is local simulation monitoring only. It does not run exchange Dry-run, use API keys, read accounts, create orders, or auto trade.

## Decision

- Local paper monitoring active: `True`
- Monitoring health: `watch`
- Continue local paper monitoring: `True`
- Exchange Dry-run review ready: `False`
- Live trading approved: `False`
- Reason: `local_paper_monitoring_continues_with_decay_warnings`
- Warning reasons: `recent_20_win_rate_below_55, recent_20_reward_risk_below_1_5, closed_fill_not_fresh, approved_signal_to_fill_lag_above_5_days, some_approved_signals_skipped_by_concurrency`
- Fail reasons: `none`

## Full Ledger Metrics

- Trades: `41`
- Win rate: `60.9756`
- Reward/risk: `1.6922`
- Profit factor: `2.644`
- Total return: `14.9788`
- Max drawdown: `3.242758`
- Max consecutive losses: `3`

## Freshness

- Latest signal: `2026-07-03T20:00:00+00:00`
- Latest closed fill: `2026-06-17T21:00:00+00:00`
- Signal age days: `1.885`
- Closed fill age days: `17.844`
- Signal to closed-fill lag days: `15.958`
- Signal fresh: `True`
- Closed fill fresh: `False`

## Rolling Windows

- Last `5` of target `5` trades: winRate=`40.0`, reward/risk=`2.5127`, PF=`1.6751`, return=`1.0305`, maxDD=`1.526414`
- Last `10` of target `10` trades: winRate=`50.0`, reward/risk=`1.1522`, PF=`1.1522`, return=`0.5865`, maxDD=`3.701227`
- Last `20` of target `20` trades: winRate=`50.0`, reward/risk=`1.3738`, PF=`1.3738`, return=`2.0495`, maxDD=`3.648788`
- Last `30` of target `30` trades: winRate=`63.3333`, reward/risk=`1.6011`, PF=`2.7655`, return=`11.6959`, maxDD=`3.337044`
- Last `40` of target `40` trades: winRate=`60.0`, reward/risk=`1.708`, PF=`2.562`, return=`14.2316`, maxDD=`3.263747`

## Skipped Signals

- `candidate_not_approved_for_local_paper`: `50`
- `max_concurrent_positions_reached`: `16`

## Pair Breakdown

- `SEI/USDT:USDT`: trades=`3`, winRate=`100.0`, PF=`None`, return=`3.0081`
- `APT/USDT:USDT`: trades=`3`, winRate=`66.6667`, PF=`5.2469`, return=`1.3506`
- `INJ/USDT:USDT`: trades=`3`, winRate=`66.6667`, PF=`8.9256`, return=`1.0486`
- `PEPE/USDT:USDT`: trades=`3`, winRate=`66.6667`, PF=`1.4131`, return=`0.4163`
- `UNI/USDT:USDT`: trades=`3`, winRate=`33.3333`, PF=`1.0069`, return=`0.0105`
- `ADA/USDT:USDT`: trades=`2`, winRate=`100.0`, PF=`None`, return=`2.0642`
- `OP/USDT:USDT`: trades=`2`, winRate=`50.0`, PF=`16.3178`, return=`1.9976`
- `SOL/USDT:USDT`: trades=`2`, winRate=`100.0`, PF=`None`, return=`1.832`
- `XRP/USDT:USDT`: trades=`2`, winRate=`100.0`, PF=`None`, return=`1.5989`
- `DOGE/USDT:USDT`: trades=`2`, winRate=`100.0`, PF=`None`, return=`0.7941`

## Next Step

- Continue local paper monitoring and collect more fresh evidence before exchange Dry-run review.

## Safety Boundary

- Local simulated capital only.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No real orders.
- No automatic trading.
- Exchange Dry-run remains disabled.
