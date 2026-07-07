# V13.5.8 Adaptive ML Factor Discovery Report

This report adds an auditable adaptive ML layer. It learns train-only factor threshold rules and validates them on later folds.

## Decision

- Adaptive ML computed: `True`
- Target R multiple unchanged: `True`
- Local paper watch approved: `False`
- Local paper watch pool: `None`
- New formal paper candidate approved: `False`
- Exchange Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `adaptive_ml_no_watch_candidate_passed`

## Adaptive Summary

- Total candidates: `7`
- Local paper watch approved count: `0`

## Timeframe Coverage

- `1h`: pairs=`28`, panelRows=`797589`, range=`2023-01-02T00:00:00+00:00` to `2026-07-05T15:00:00+00:00`, adaptiveCandidates=`3`
- `4h`: pairs=`38`, panelRows=`358601`, range=`2020-01-05T00:00:00+00:00` to `2026-07-05T16:00:00+00:00`, adaptiveCandidates=`4`

## Top Adaptive Candidates

- `1h:adaptive_ml_all_high_reward:sl0.025:h30`: selectedTrades=`1275`, winRate=`36.7059`, RR=`1.6143`, PF=`0.9362`, maxDD=`98.3195`, baselinePF=`0.8514`, folds=`4`, 2Rclose=`0.908044`, watch=`False`, fail=`win_rate_below_45, profit_factor_below_1_45, max_drawdown_above_45, total_return_not_positive`
- `1h:adaptive_ml_all_high_reward:sl0.02:h24`: selectedTrades=`1277`, winRate=`36.0219`, RR=`1.6325`, PF=`0.9191`, maxDD=`94.731`, baselinePF=`0.8113`, folds=`4`, 2Rclose=`0.945132`, watch=`False`, fail=`win_rate_below_45, profit_factor_below_1_45, max_drawdown_above_45, total_return_not_positive`
- `1h:adaptive_ml_all_high_reward:sl0.03:h36`: selectedTrades=`427`, winRate=`33.7237`, RR=`1.7413`, PF=`0.886`, maxDD=`90.735`, baselinePF=`0.8469`, folds=`4`, 2Rclose=`0.960717`, watch=`False`, fail=`win_rate_below_45, profit_factor_below_1_45, max_drawdown_above_45, total_return_not_positive`
- `4h:adaptive_ml_all_high_reward:sl0.08:h30`: selectedTrades=`533`, winRate=`37.8987`, RR=`1.3936`, PF=`0.8505`, maxDD=`99.8856`, baselinePF=`1.0272`, folds=`4`, 2Rclose=`0.723261`, watch=`False`, fail=`win_rate_below_45, profit_factor_below_1_45, max_drawdown_above_45, total_return_not_positive`
- `4h:adaptive_ml_all_high_reward:sl0.04:h12`: selectedTrades=`601`, winRate=`34.609`, RR=`1.4228`, PF=`0.753`, maxDD=`99.2819`, baselinePF=`0.9237`, folds=`4`, 2Rclose=`0.766123`, watch=`False`, fail=`win_rate_below_45, profit_factor_below_1_45, max_drawdown_above_45, total_return_not_positive`
- `4h:adaptive_ml_all_high_reward:sl0.06:h24`: selectedTrades=`518`, winRate=`36.8726`, RR=`1.286`, PF=`0.7511`, maxDD=`99.8059`, baselinePF=`1.0178`, folds=`4`, 2Rclose=`0.675695`, watch=`False`, fail=`win_rate_below_45, profit_factor_below_1_45, max_drawdown_above_45, total_return_not_positive, observed_rr_not_close_to_cost_adjusted_2r`
- `4h:adaptive_ml_all_high_reward:sl0.05:h18`: selectedTrades=`488`, winRate=`29.7131`, RR=`1.4199`, PF=`0.6002`, maxDD=`99.9419`, baselinePF=`0.9818`, folds=`4`, 2Rclose=`0.753416`, watch=`False`, fail=`win_rate_below_45, profit_factor_below_1_45, max_drawdown_above_45, total_return_not_positive`

## Strategy Evolution

- Future local paper and manual-review outcomes can be stored with `strategy_evolution_sample_v1`.
- Historical labels are not fabricated actual trades.
- Retraining must remain offline and cannot create orders.

## Recommendations

- Adaptive factor learning ran, but no candidate passed the local paper watch gate.
- Keep collecting public data and use paper/manual outcomes as future training samples after independent validation.
- Best observed adaptive pool 1h:adaptive_ml_all_high_reward:sl0.025:h30: trades=1275, winRate=36.7059, PF=0.9362, RR=1.6143, maxDD=98.3195.

## Safety Boundary

- Public local data only.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account or position reads.
- No order creation.
- No automatic trading.
