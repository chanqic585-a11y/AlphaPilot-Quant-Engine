# Research Factor vs Trading Signal

A research factor is not a trading signal.

## Research Factor

A factor is a numeric feature used to study historical market structure. In
V13.4.22, factors are evaluated for coverage, RankIC, quantile spread,
stability, and TP/SL label relationships.

## Trading Signal

A trading signal would require strategy rules, execution assumptions, risk
controls, backtesting, slippage tests, shadow trading evidence, and separate
approval gates. V13.4.22 does not do any of that.

## V13.4.22 Decision

The V13.4.22 report found no factor that passed the research candidate gate.
Even if a factor had passed, it would still be:

```text
research_only
not_trade_ready
not_dry_run_ready
```

No factor should be promoted directly into an entry rule. The next safer step
is a benchmark strategy suite or a separate factor-based hypothesis design
phase.

