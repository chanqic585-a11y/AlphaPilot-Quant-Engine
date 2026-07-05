# V13.5.12 Active Alpha Overlay Replay Report

This report rebuilds the active V13.5.7 alpha overlay event log and replays it through local paper accounting.
It is historical replay only, not forward validation, exchange Dry-run, or live trading.

## Active Pool

- Pool id: `4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24`
- Overlay id: `alpha_short_exhaustion_pressure_watch`
- Timeframe: `4h`
- Stop loss: `0.06`
- Target R: `2.0`
- Horizon bars: `24`

## Event Summary

- All high-reward events: `12977`
- Active overlay events: `145`
- Event win rate: `58.6207`
- Event profit factor: `2.5793`
- Event reward/risk: `1.8207`

## Local Paper Replay

- Mode: `historical_replay_not_forward_validation`
- Filled signals: `131`
- Closed trades: `131`
- Win rate: `58.7786`
- Profit factor: `2.5656`
- Reward/risk: `1.7992`
- Total return: `116.4183`
- Max drawdown: `6.82632`
- Skipped signals: `14`

## Decision

- Replay completed: `True`
- Historical replay only: `True`
- Active strategy samples prepared: `145`
- Ready for exchange Dry-run review: `False`
- Exchange Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `active_strategy_historical_replay_ready_but_forward_local_paper_still_required`

## Safety Boundary

- Public local data only.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No real orders.
- No automatic trading.
