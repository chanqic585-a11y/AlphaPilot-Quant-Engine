# V13.5.5 Event Pool Expansion Report

This report expands public historical event samples and checks anti-overfit coverage. It does not approve exchange Dry-run or live trading.

## Decision

- Event pool expanded: `True`
- Sample sufficiency ready: `True`
- New local paper candidate approved: `False`
- Continue existing local paper monitoring: `True`
- Exchange Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `sample_sufficient_event_pools_available`

## Event Pool Summary

- Total pools: `28`
- Sample-sufficient pools: `28`
- Target-metric pools: `0`

## Timeframe Coverage

- `1h`: pairs=`28`, panelRows=`797729`, range=`2023-01-01T19:00:00+00:00` to `2026-07-05T15:00:00+00:00`, pools=`16`
- `4h`: pairs=`28`, panelRows=`198775`, range=`2023-01-04T04:00:00+00:00` to `2026-07-04T12:00:00+00:00`, pools=`12`

## Top Event Pools

- `1h:all_setups:sl0.04:h30`: trades=`64657`, winRate=`41.5639`, RR=`1.2824`, PF=`0.9122`, maxDD=`100.0`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`
- `1h:all_setups:sl0.03:h24`: trades=`64657`, winRate=`39.2595`, RR=`1.3702`, PF=`0.8856`, maxDD=`100.0`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`
- `1h:all_setups:sl0.025:h18`: trades=`64657`, winRate=`38.1707`, RR=`1.3682`, PF=`0.8447`, maxDD=`100.0`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`
- `1h:all_setups:sl0.02:h12`: trades=`64657`, winRate=`37.1298`, RR=`1.3631`, PF=`0.805`, maxDD=`100.0`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`
- `4h:all_setups:sl0.06:h24`: trades=`24308`, winRate=`39.5549`, RR=`1.4475`, PF=`0.9472`, maxDD=`100.0`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`
- `4h:all_setups:sl0.05:h18`: trades=`24308`, winRate=`38.6539`, RR=`1.4497`, PF=`0.9134`, maxDD=`100.0`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`
- `4h:all_setups:sl0.04:h12`: trades=`24308`, winRate=`38.3043`, RR=`1.4037`, PF=`0.8715`, maxDD=`100.0`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`
- `1h:long_continuation_candidate:sl0.03:h24`: trades=`22787`, winRate=`40.3168`, RR=`1.2518`, PF=`0.8456`, maxDD=`100.0`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`
- `1h:long_continuation_candidate:sl0.04:h30`: trades=`22787`, winRate=`41.2296`, RR=`1.2002`, PF=`0.842`, maxDD=`100.0`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`
- `1h:long_continuation_candidate:sl0.025:h18`: trades=`22787`, winRate=`39.7683`, RR=`1.2586`, PF=`0.831`, maxDD=`100.0`, sampleReady=`True`, targetReady=`False`, fail=`none`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`

## Highest Reward/Risk Pools

- `4h:short_reversal_candidate:sl0.05:h18`: trades=`11335`, winRate=`40.0529`, RR=`1.5681`, PF=`1.0477`, maxDD=`100.0`, targetReady=`False`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50`
- `4h:short_reversal_candidate:sl0.06:h24`: trades=`11335`, winRate=`42.0468`, RR=`1.5577`, PF=`1.1301`, maxDD=`100.0`, targetReady=`False`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25`
- `4h:short_reversal_candidate:sl0.04:h12`: trades=`11335`, winRate=`39.5765`, RR=`1.5219`, PF=`0.9968`, maxDD=`100.0`, targetReady=`False`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50`
- `1h:short_reversal_candidate:sl0.03:h24`: trades=`21686`, winRate=`39.7353`, RR=`1.4908`, PF=`0.9829`, maxDD=`100.0`, targetReady=`False`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50`
- `1h:short_reversal_candidate:sl0.025:h18`: trades=`21686`, winRate=`37.9369`, RR=`1.4897`, PF=`0.9106`, maxDD=`100.0`, targetReady=`False`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50`
- `1h:short_reversal_candidate:sl0.02:h12`: trades=`21686`, winRate=`37.0193`, RR=`1.4746`, PF=`0.8668`, maxDD=`100.0`, targetReady=`False`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`
- `4h:all_setups:sl0.05:h18`: trades=`24308`, winRate=`38.6539`, RR=`1.4497`, PF=`0.9134`, maxDD=`100.0`, targetReady=`False`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`
- `4h:all_setups:sl0.06:h24`: trades=`24308`, winRate=`39.5549`, RR=`1.4475`, PF=`0.9472`, maxDD=`100.0`, targetReady=`False`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`
- `4h:all_setups:sl0.04:h12`: trades=`24308`, winRate=`38.3043`, RR=`1.4037`, PF=`0.8715`, maxDD=`100.0`, targetReady=`False`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`
- `4h:long_continuation_candidate:sl0.05:h18`: trades=`3254`, winRate=`40.1352`, RR=`1.3898`, PF=`0.9317`, maxDD=`100.0`, targetReady=`False`, targetFail=`win_rate_below_45, reward_risk_below_2_0, profit_factor_below_1_35, max_drawdown_above_25, total_return_not_positive, recent_win_rate_below_50, recent_profit_factor_below_1`

## Recommendations

- Event sample breadth is now enough for forward research, but target metrics did not fully pass.
- Keep local paper monitoring active and refresh public data again before any Dry-run review.
- Best sample-sufficient pool 1h:all_setups:sl0.04:h30: trades=64657, winRate=41.5639, rewardRisk=1.2824, profitFactor=0.9122, maxDrawdown=100.0.

## Safety Boundary

- Public local market data only.
- No API key storage.
- No Trade API.
- No Withdraw API.
- No real account reads.
- No real position reads.
- No real orders.
- No automatic trading.
- Exchange Dry-run remains disabled.
