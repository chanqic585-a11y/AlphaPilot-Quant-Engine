# No-Lookahead Forward Labels

V13.4.22 separates point-in-time features from forward-looking evaluation
labels.

## Feature Rule

Factor columns can use only current and historical data. Rolling calculations
are computed inside each pair using past rows and the current row. Cross
sectional ranks use only pairs visible at the same timestamp.

## Label Rule

Forward labels intentionally use future candles, but only as evaluation
targets. They never flow back into:

- factor calculation
- factor panel filtering
- universe construction
- sample selection
- strategy logic
- Dry-run approval

## TP/SL Labels

The label builder records whether a +5% TP or -2.5% SL level is touched first
inside each forward window. If TP and SL are both touched in the same candle,
the label uses a conservative SL-first rule.

These labels are not orders, recommendations, or execution instructions.

## Boundary

Features are point-in-time. Labels are forward-looking for evaluation only.
This boundary is mandatory before any later benchmark or strategy hypothesis
work.

