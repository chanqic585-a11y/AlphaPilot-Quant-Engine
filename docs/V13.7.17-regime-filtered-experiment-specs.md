# V13.7.17 v13_7_17_regime_filtered_experiment_specs

Define explicit research experiment specs before writing new strategy code.

## Summary

- experimentSpecCount: 3
- readyForBacktestImplementationCount: 3
- paperObservationAllowedCount: 0
- dryRunApproved: False
- liveTradingApproved: False
- nextStep: Implement and backtest one experiment at a time; do not move to paper observation from specs alone.

## Safety Boundary

- No Trade API.
- No Withdraw API.
- No exchange API key storage.
- No real account or position reads.
- No order creation.
- No exchange Dry-run execution.
- No live or automatic trading.
