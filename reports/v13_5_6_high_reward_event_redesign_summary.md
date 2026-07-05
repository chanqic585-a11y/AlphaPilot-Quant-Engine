# V13.5.6 High Reward Event Redesign Report

This report keeps the target at 2R and tests redesigned high-reward event structures on local public data.
It is research-only and does not approve exchange Dry-run or live trading.

## Decision

- High reward redesign completed: `True`
- Target R multiple unchanged: `True`
- Sample sufficiency ready: `True`
- Forward confirmation candidate found: `False`
- New local paper candidate approved: `False`
- Exploratory local paper watch approved: `True`
- Exploratory local paper watch pool: `1h:hr_long_extreme_volume_btc_crash_rebound:sl0.02:h24`
- Exchange Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `exploratory_local_paper_watch_only`

## Event Pool Summary

- Total pools: `63`
- Sample-sufficient pools: `63`
- Target-metric pools: `0`
- Highest cost-adjusted 2R closeness: `1.012926`

## Timeframe Coverage

- `1h`: pairs=`28`, panelRows=`797589`, range=`2023-01-02T00:00:00+00:00` to `2026-07-05T15:00:00+00:00`, pools=`35`
- `4h`: pairs=`28`, panelRows=`198635`, range=`2023-01-05T00:00:00+00:00` to `2026-07-04T12:00:00+00:00`, pools=`28`

## Top Event Pools

- `1h:hr_short_trend_pullback_acceleration:sl0.05:h60`: trades=`5082`, winRate=`44.2542`, RR=`1.4861`, PF=`1.1797`, maxDD=`99.9998`, 2Rclose=`0.788543`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, profit_factor_below_1_35, max_drawdown_above_30, observed_rr_not_close_to_cost_adjusted_2r`
- `4h:hr_short_failed_breakout_rejection:sl0.08:h30`: trades=`2660`, winRate=`45.3383`, RR=`1.3782`, PF=`1.1431`, maxDD=`99.9996`, 2Rclose=`0.715268`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`profit_factor_below_1_35, max_drawdown_above_30, observed_rr_not_close_to_cost_adjusted_2r`
- `4h:hr_short_failed_breakout_rejection:sl0.06:h24`: trades=`2660`, winRate=`43.6842`, RR=`1.4664`, PF=`1.1375`, maxDD=`99.9811`, 2Rclose=`0.770481`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, profit_factor_below_1_35, max_drawdown_above_30, observed_rr_not_close_to_cost_adjusted_2r`
- `1h:hr_short_trend_pullback_acceleration:sl0.04:h48`: trades=`5082`, winRate=`41.3617`, RR=`1.604`, PF=`1.1314`, maxDD=`99.9739`, 2Rclose=`0.863692`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, profit_factor_below_1_35, max_drawdown_above_30`
- `4h:hr_short_blowoff_reversal:sl0.08:h30`: trades=`2403`, winRate=`42.4053`, RR=`1.5006`, PF=`1.1048`, maxDD=`100.0`, 2Rclose=`0.778792`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, profit_factor_below_1_35, max_drawdown_above_30, total_return_not_positive, observed_rr_not_close_to_cost_adjusted_2r`
- `4h:hr_short_trend_pullback_acceleration:sl0.06:h24`: trades=`1726`, winRate=`42.0046`, RR=`1.521`, PF=`1.1016`, maxDD=`99.9999`, 2Rclose=`0.799169`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, profit_factor_below_1_35, max_drawdown_above_30, observed_rr_not_close_to_cost_adjusted_2r`
- `4h:hr_short_trend_pullback_acceleration:sl0.05:h18`: trades=`1726`, winRate=`42.0046`, RR=`1.5199`, PF=`1.1008`, maxDD=`99.9961`, 2Rclose=`0.806478`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, profit_factor_below_1_35, max_drawdown_above_30, observed_rr_not_close_to_cost_adjusted_2r`
- `4h:hr_short_blowoff_reversal:sl0.06:h24`: trades=`2403`, winRate=`39.742`, RR=`1.6276`, PF=`1.0734`, maxDD=`99.9998`, 2Rclose=`0.85518`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, profit_factor_below_1_35, max_drawdown_above_30, total_return_not_positive`
- `4h:hr_short_failed_breakout_rejection:sl0.05:h18`: trades=`2660`, winRate=`41.4662`, RR=`1.5109`, PF=`1.0703`, maxDD=`99.9125`, 2Rclose=`0.801702`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, profit_factor_below_1_35, max_drawdown_above_30, observed_rr_not_close_to_cost_adjusted_2r`
- `1h:hr_short_trend_pullback_acceleration:sl0.03:h36`: trades=`5082`, winRate=`38.5872`, RR=`1.6984`, PF=`1.0672`, maxDD=`99.9408`, 2Rclose=`0.937048`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, profit_factor_below_1_35, max_drawdown_above_30`
- `1h:hr_short_trend_pullback_acceleration:sl0.025:h30`: trades=`5082`, winRate=`38.9807`, RR=`1.6667`, PF=`1.0647`, maxDD=`99.826`, 2Rclose=`0.937519`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, profit_factor_below_1_35, max_drawdown_above_30`
- `4h:hr_short_trend_pullback_acceleration:sl0.08:h30`: trades=`1726`, winRate=`41.8888`, RR=`1.4567`, PF=`1.0501`, maxDD=`100.0`, 2Rclose=`0.756009`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, profit_factor_below_1_35, max_drawdown_above_30, total_return_not_positive, observed_rr_not_close_to_cost_adjusted_2r`

## Exploratory Fixed Filters

- `1h:hr_long_extreme_volume_btc_crash_rebound:sl0.02:h24`: trades=`162`, winRate=`70.9877`, RR=`1.6128`, PF=`3.9462`, maxDD=`32.9962`, recentTrades=`33`, recentPF=`1.1227`, paperWatch=`True`, watchFail=`none`
- `1h:hr_long_extreme_volume_btc_crash_rebound:sl0.025:h30`: trades=`162`, winRate=`70.3704`, RR=`1.5874`, PF=`3.77`, maxDD=`38.9014`, recentTrades=`33`, recentPF=`1.1556`, paperWatch=`False`, watchFail=`observed_rr_not_close_enough_to_cost_adjusted_2r`
- `1h:hr_long_extreme_volume_btc_crash_rebound:sl0.05:h60`: trades=`162`, winRate=`67.284`, RR=`1.5892`, PF=`3.2683`, maxDD=`61.7572`, recentTrades=`33`, recentPF=`1.4609`, paperWatch=`False`, watchFail=`max_drawdown_above_40, observed_rr_not_close_enough_to_cost_adjusted_2r`
- `1h:hr_long_extreme_volume_btc_crash_rebound:sl0.03:h36`: trades=`162`, winRate=`64.1975`, RR=`1.5954`, PF=`2.8607`, maxDD=`44.3127`, recentTrades=`33`, recentPF=`1.1781`, paperWatch=`False`, watchFail=`max_drawdown_above_40, observed_rr_not_close_enough_to_cost_adjusted_2r`
- `1h:hr_long_extreme_volume_btc_crash_rebound:sl0.04:h48`: trades=`162`, winRate=`62.3457`, RR=`1.6617`, PF=`2.7513`, maxDD=`53.8067`, recentTrades=`33`, recentPF=`1.5476`, paperWatch=`False`, watchFail=`max_drawdown_above_40, observed_rr_not_close_enough_to_cost_adjusted_2r`
- `4h:hr_short_sideways_breakout_reject_btc_up:sl0.08:h30`: trades=`125`, winRate=`64.8`, RR=`1.4489`, PF=`2.6672`, maxDD=`39.5354`, recentTrades=`25`, recentPF=`2.0173`, paperWatch=`False`, watchFail=`observed_rr_not_close_enough_to_cost_adjusted_2r`
- `4h:hr_short_extreme_volume_relative_strength_basis_low:sl0.06:h24`: trades=`165`, winRate=`57.5758`, RR=`1.8444`, PF=`2.5031`, maxDD=`38.3157`, recentTrades=`33`, recentPF=`3.4442`, paperWatch=`True`, watchFail=`none`
- `4h:hr_short_overheated_extreme_volume_basis_low:sl0.06:h24`: trades=`154`, winRate=`57.7922`, RR=`1.8`, PF=`2.4646`, maxDD=`47.3484`, recentTrades=`31`, recentPF=`2.0421`, paperWatch=`False`, watchFail=`max_drawdown_above_40`

## Recommendations

- A fixed exploratory filter is approved for local paper watch only; it is not a new formal paper candidate and not exchange Dry-run.
- Keep the 2R target unchanged and monitor the next forward signals before any promotion decision.
- Paper-watch pool 1h:hr_long_extreme_volume_btc_crash_rebound:sl0.02:h24: trades=162, winRate=70.9877, PF=3.9462, maxDD=32.9962.

## Safety Boundary

- Public local data only.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account or position reads.
- No order creation.
- No automatic trading.
