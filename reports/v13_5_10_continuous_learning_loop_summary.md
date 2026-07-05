# V13.5.10 Continuous Learning Loop Report

This report converts local paper outcomes into strategy evolution samples.
It does not retrain a model, use API keys, call exchange APIs, create orders, or auto trade.

## Learning State

- Learning loop computed: `True`
- Active strategy: `v13_5_7_alpha_overlay_fixed_watch`
- Active candidate pool: `4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24`
- Observer strategies: `v13_5_8_adaptive_ml_observer`
- Strategy evolution dataset updated: `True`
- New local paper samples: `41`
- Usable local paper samples: `41`
- Active strategy samples: `0`
- Active strategy usable samples: `0`
- Ready for retraining: `False`
- Continue local paper monitoring: `True`
- Exchange Dry-run review ready: `False`
- Exchange Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `learning_dataset_prepared_but_not_ready_for_retraining`

## Sample Summary

- Total samples: `41`
- Usable for retraining: `41`
- Active strategy samples: `0`
- Active strategy usable samples: `0`
- Outcome labels: `{'loss': 16, 'positive_under_two_r': 24, 'two_r_or_better': 1}`
- Pair breakdown: `{'ADA/USDT:USDT': 2, 'APT/USDT:USDT': 3, 'ATOM/USDT:USDT': 1, 'AVAX/USDT:USDT': 1, 'BCH/USDT:USDT': 1, 'BTC/USDT:USDT': 1, 'DOGE/USDT:USDT': 2, 'DOT/USDT:USDT': 2, 'ETC/USDT:USDT': 1, 'ETH/USDT:USDT': 2, 'FIL/USDT:USDT': 1, 'INJ/USDT:USDT': 3, 'LINK/USDT:USDT': 1, 'LTC/USDT:USDT': 1, 'OP/USDT:USDT': 2, 'ORDI/USDT:USDT': 1, 'PEPE/USDT:USDT': 3, 'SEI/USDT:USDT': 3, 'SOL/USDT:USDT': 2, 'SUI/USDT:USDT': 1, 'TIA/USDT:USDT': 1, 'UNI/USDT:USDT': 3, 'WIF/USDT:USDT': 1, 'XRP/USDT:USDT': 2}`
- Strategy breakdown: `{'v13_5_1_1h_short_reversal_bull_relative_return': 41}`

## Retraining Gate

- Ready: `False`
- Minimum usable samples: `100`
- Usable samples: `41`
- Active strategy usable samples: `0`
- Latest exit time: `2026-06-17T21:00:00+00:00`
- Monitoring health: `watch`
- Fail reasons: `insufficient_usable_local_paper_samples, active_strategy_has_no_closed_local_paper_samples, closed_fill_not_fresh`
- Warning reasons: `monitoring_health_not_healthy`
- Allowed next action: `prepare_more_local_paper_outcomes`

## Strategy Roles

- `v13_5_7_alpha_overlay_fixed_watch`
  - role: `active_local_paper_watch`
  - candidatePoolId: `4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24`
  - canCreateOrders: `False`
  - canTriggerDryRun: `False`
- `v13_5_8_adaptive_ml_observer`
  - role: `observer_only`
  - candidatePoolId: `None`
  - canCreateOrders: `False`
  - canTriggerDryRun: `False`

## Recommendations

- Continue local paper monitoring until fresh closed fills accumulate.
- Do not retrain from fewer than 100 usable local paper outcome samples.
- Use the generated samples as offline research data only.
- Keep V13.5.8 adaptive ML observer-only until it independently improves on the active watch strategy.
- Do not move to exchange Dry-run or live trading from this report.

## Safety Boundary

- Local paper outcomes only.
- No real trade outcomes are claimed.
- No model retraining is performed by this report.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No real orders.
- No emergency close implementation.
- No testnet execution implementation.
- No automatic trading.
