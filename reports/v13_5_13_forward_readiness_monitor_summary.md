# V13.5.13 Forward Readiness Monitor

This monitor checks whether enough post-selection public candles exist for closed forward local paper samples.
It does not create orders, use API keys, or auto trade.

## Active Pool

- Pool id: `4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24`
- Timeframe: `4h`
- Horizon bars: `24`
- Stop loss: `0.06`
- Target R: `2.0`

## Forward Horizon

- Selection time: `2026-07-05T20:13:33.701790+00:00`
- Required horizon hours: `96.0`
- Earliest closed sample time: `2026-07-09T20:13:33.701790+00:00`
- Latest local candle: `2026-07-05T16:00:00+00:00`
- Loaded pairs: `28`
- Ready pair count: `0`

## Decision

- Forward closed samples possible: `False`
- Ready for forward local paper refresh: `False`
- Exchange Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `not_enough_post_selection_4h_candles_for_closed_forward_samples`

## Safety Boundary

- Public local data only.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No real orders.
- No automatic trading.
