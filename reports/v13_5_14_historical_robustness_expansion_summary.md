# V13.5.14 Historical Robustness Expansion

This report expands historical diagnostics for the fixed active V13.5.7 strategy.
It is historical research only. It is not forward validation, exchange Dry-run, or live trading.

## Active Pool

- Pool id: `4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24`
- Timeframe: `4h`
- Overlay id: `alpha_short_exhaustion_pressure_watch`
- Stop loss: `0.06`
- Target R: `2.0`
- Horizon bars: `24`

## Historical Event Metrics

- Active overlay events: `146`
- Trade count: `146`
- Win rate: `58.9041`
- Profit factor: `2.5851`
- Reward/risk: `1.8036`
- Total return: `10773.0478`
- Max drawdown: `38.3157`
- Event pairs: `25`
- Unique months: `40`
- Range: `2023-01-09T20:00:00+00:00` to `2026-07-04T16:00:00+00:00`

## Robustness Slices

- `early60`: trades=`87`, winRate=`56.3218`, PF=`2.3137`, RR=`1.7943`
- `middle20`: trades=`29`, winRate=`62.069`, PF=`2.8694`, RR=`1.7535`
- `recent20`: trades=`30`, winRate=`63.3333`, PF=`3.262`, RR=`1.8885`

## Walk-Forward Review

- Method: `chronological_60_20_20_fixed_parameters`
- Passed: `True`
- Gate warnings: `none`
- Train PF: `2.3137`
- Validation PF: `2.8694`
- Test PF: `3.262`

## Market-State Slices

- `bull`: trades=`90`, winRate=`60.0`, PF=`2.8114`, return=`2151.4332`
- `alt_rotation_strength`: trades=`30`, winRate=`60.0`, PF=`2.4417`, return=`145.2431`
- `bear`: trades=`25`, winRate=`56.0`, PF=`2.3037`, return=`109.1814`
- `btc_sharp_drop`: trades=`1`, winRate=`0.0`, PF=`0.0`, return=`-5.8604`

## Stress Tests

- `base_recorded`: winRate=`58.9041`, PF=`2.585115`, simpleReturn=`526.70278`, maxSingleLoss=`-5.860377`
- `fee_slippage_plus_0_10pct`: winRate=`58.9041`, PF=`2.51384`, simpleReturn=`512.10278`, maxSingleLoss=`-5.960377`
- `fee_slippage_plus_0_30pct`: winRate=`58.2192`, PF=`2.378313`, simpleReturn=`482.90278`, maxSingleLoss=`-6.160377`
- `entry_delay_plus_0_20pct`: winRate=`58.9041`, PF=`2.44505`, simpleReturn=`497.50278`, maxSingleLoss=`-6.060377`
- `extreme_gap_losses_1_25x`: winRate=`58.9041`, PF=`2.068092`, simpleReturn=`443.632636`, maxSingleLoss=`-7.325471`
- `combined_conservative`: winRate=`58.2192`, PF=`1.801116`, simpleReturn=`363.063338`, maxSingleLoss=`-7.950471`

## Factor Outcome Separation

- `ts_volume_ratio_rank_24`: availability=`100.0`, winnerMean=`0.95155`, loserMean=`0.972222`, separation=`-0.431422`
- `decay_volume_pressure_12`: availability=`100.0`, winnerMean=`1.228485`, loserMean=`1.0762`, separation=`0.409926`
- `ts_return_volume_corr_24`: availability=`100.0`, winnerMean=`-0.091818`, loserMean=`0.035251`, separation=`-0.381484`
- `decay_return_12`: availability=`100.0`, winnerMean=`0.014894`, loserMean=`0.018035`, separation=`-0.313212`
- `cs_return_3_rank`: availability=`100.0`, winnerMean=`0.964507`, loserMean=`0.975018`, separation=`-0.233427`
- `ts_close_location_rank_24`: availability=`100.0`, winnerMean=`0.37936`, loserMean=`0.425694`, separation=`-0.180067`
- `cs_mark_basis_rank`: availability=`100.0`, winnerMean=`0.123002`, loserMean=`0.138023`, separation=`-0.165867`
- `alpha_exhaustion_pressure`: availability=`100.0`, winnerMean=`0.516975`, loserMean=`0.492885`, separation=`0.118134`
- `ts_return_12_rank_24`: availability=`100.0`, winnerMean=`0.92781`, loserMean=`0.940972`, separation=`-0.111161`
- `ts_bollinger_z_rank_24`: availability=`100.0`, winnerMean=`0.875969`, loserMean=`0.888889`, separation=`-0.101446`

## Top Pair Slices

- `INJ/USDT:USDT`: trades=`11`, winRate=`63.6364`, PF=`3.8345`, return=`82.8504`
- `OP/USDT:USDT`: trades=`10`, winRate=`30.0`, PF=`0.8172`, return=`-10.0762`
- `UNI/USDT:USDT`: trades=`9`, winRate=`88.8889`, PF=`11.8589`, return=`82.325`
- `ETC/USDT:USDT`: trades=`9`, winRate=`77.7778`, PF=`5.0957`, return=`56.353`
- `DOT/USDT:USDT`: trades=`9`, winRate=`77.7778`, PF=`4.1631`, return=`41.2402`
- `PEPE/USDT:USDT`: trades=`9`, winRate=`66.6667`, PF=`3.2079`, return=`41.8309`
- `ORDI/USDT:USDT`: trades=`9`, winRate=`55.5556`, PF=`2.8659`, return=`47.5201`
- `TIA/USDT:USDT`: trades=`8`, winRate=`50.0`, PF=`2.2927`, return=`30.0466`
- `AAVE/USDT:USDT`: trades=`8`, winRate=`25.0`, PF=`0.8055`, return=`-8.7114`
- `ATOM/USDT:USDT`: trades=`6`, winRate=`83.3333`, PF=`5.7195`, return=`29.2562`

## Cross-Market Public Context

- Cache dir: `user_data\cross_market_data\v13_5_11`
- Symbols loaded: `8` / `8`
- `cn_a_share`: valid=`2`, avgQuality=`100.0`, avg60dReturn=`-12.826194`, avg60dVol=`20.063688`
- `hk_stock`: valid=`2`, avgQuality=`100.0`, avg60dReturn=`-18.239218`, avg60dVol=`41.63964`
- `index`: valid=`2`, avgQuality=`100.0`, avg60dReturn=`2.704043`, avg60dVol=`15.968593`
- `us_etf`: valid=`2`, avgQuality=`100.0`, avg60dReturn=`17.023985`, avg60dVol=`18.941194`

## Decision

- Historical robustness expansion completed: `True`
- Active strategy fixed parameters: `True`
- Historical robustness watch passed: `True`
- Forward validation still required: `True`
- Ready for exchange Dry-run review: `False`
- Exchange Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `historical_robustness_expanded_but_forward_samples_still_required`
- Warnings: `none`

## Recommendations

- Keep the active pool parameters fixed; do not tune thresholds against this expanded historical report.
- Use cross-market public data as factor and regime inspiration only until normalization and separate validation are added.
- Continue waiting for closed post-selection 4h forward samples before any exchange Dry-run review.
- If historical warnings appear, treat them as robustness risks, not as a reason to lower the 2R target.

## Safety Boundary

- Public local data only.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account or position reads.
- No real order creation.
- No automatic trading.
