# Factor Evaluation Methodology

V13.4.22 evaluates each manual factor with the same forward-label set and the
same cross-sectional process.

## Forward Horizons

The default horizons are:

- 4 bars
- 8 bars
- 12 bars
- 24 bars

On the default `1h` timeframe, these correspond to 4h, 8h, 12h, and 24h
research windows.

## Metrics

For each factor, the evaluator reports:

- coverage percentage
- missing rate
- cross-sectional IC
- cross-sectional RankIC
- forward return mean and median by horizon
- Q1-Q5 quantile return table
- Q5-Q1 spread
- monotonicity score
- TP before SL probability
- SL before TP probability
- profit factor approximation
- expectancy
- stability by month, pair, regime, and universe membership

IC and RankIC are calculated cross-sectionally per timestamp and then
summarized. The report does not use one global mixed-row correlation as the
only factor-quality metric.

## Candidate Gate

The first research gate requires:

- coverage at least 80%
- at least 1,000 valid samples
- absolute mean RankIC at least 0.02
- positive RankIC ratio at least 0.55
- Q5-Q1 spread above 0
- profit factor above 1.05

Strict candidates also require stronger RankIC, stronger profit factor, and
stability across months and pairs.

All candidate outputs are explicitly marked:

```text
research_only
not_trade_ready
not_dry_run_ready
```

This method measures factor research quality. It does not create a trading
signal.

