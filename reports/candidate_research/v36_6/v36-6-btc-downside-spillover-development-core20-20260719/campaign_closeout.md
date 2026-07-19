# V36.6 BTC Downside-Spillover Closeout

## Decision

No candidate qualified for Formal validation.

The campaign used the existing fixed-core 20-asset 1h dataset through a hash-verified reference snapshot. It did not download or duplicate market data. Six preregistered Development trials were completed.

## Evidence summary

- Candidates: 2
- Development trials: 6
- Stable selections: 0
- Formal runs: 0
- Locked OOS reads: 0
- Releases, Demo releases and orders: 0

The source replication produced one marginally positive center point: profit factor 1.034 and average net result +0.007R. It was rejected because both adjacent scales were negative and only one of three subperiods was positive. The crypto adaptation was negative at all three scales.

## Interpretation

The isolated positive center point is not a reusable strategy. It is a brittle parameter observation without neighborhood or subperiod support. Promoting it would violate the preregistered stability gate and increase overfitting risk.

The bounded OHLCV-only downside-spillover family is closed. Further work requires a new data capability or an independently preregistered market mechanism, not another threshold rescue.
