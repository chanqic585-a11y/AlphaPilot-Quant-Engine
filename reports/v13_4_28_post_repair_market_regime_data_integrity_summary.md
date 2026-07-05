# AlphaPilot V13.4.27 Market Regime and Data Integrity Review

Status: completed_with_warnings

V13.4.27 is a research-only data integrity and market regime review. It does
not implement a strategy, run a backtest, enter Dry-run, download data, call
exchange APIs, read accounts, create orders, or auto trade.

## Scope

- timerange: 20260101-
- dataPath: user_data\data\okx\futures
- timeframesChecked: 1h, 4h

## OHLCV Integrity

- status: warning
- pairCount: 30
- pairTimeframeCount: 60
- validCount: 55
- warningCount: 1
- invalidCount: 0
- missingFileCount: 4
- averageMissingRatePct: 0.0
- maxMissingRatePct: 0.0
- totalDuplicateTimestamps: 0
- totalInvalidOhlcRows: 0
- totalExtremeReturnRows: 1
- pairFormatIssueCount: 0
- spotSwapMismatchCount: 0

Warnings:

- 4 pair/timeframe files are missing locally.

## BTC Regime

- status: available
- dominantRegimes: bear, sideways, bull
- regimeDistribution: {'bear': 521, 'sideways': 411, 'bull': 266, 'high_volatility': 217, 'unknown': 193, 'crash': 29, 'recovery': 2}

BTC sanity points:

- 2025-10-01: 87805.9 at 2026-01-01T00:00:00+00:00 warning=No BTC candle within 31 days of requested checkpoint.
- 2026-01-01: 87805.9 at 2026-01-01T00:00:00+00:00 warning=None
- 2026-04-01: 68130.4 at 2026-04-01T00:00:00+00:00 warning=None
- 2026-06-01: 73722.2 at 2026-06-01T00:00:00+00:00 warning=None
- 2026-07-01: 59168.3 at 2026-07-01T00:00:00+00:00 warning=None

Regime warnings:

- BTC sanity warning for 2025-10-01: No BTC candle within 31 days of requested checkpoint.

## Dynamic Universe Breadth Proxy

{
  "status": "available",
  "source": "local_1h_ohlcv_breadth_proxy",
  "limitation": "Breadth is computed from locally available pairs, not from an exchange-wide historical universe snapshot.",
  "pairCount": 28,
  "snapshotCount": 4436,
  "latestSnapshot": {
    "timestamp": "2026-07-04T19:00:00+00:00",
    "pairCount": 3,
    "positiveReturn24hPct": 66.6667,
    "averageReturn24hPct": 1.2437,
    "medianReturn24hPct": 1.756,
    "aboveEma50Pct": 100.0,
    "aboveEma200Pct": 100.0
  },
  "averagePositiveReturn24hPct": 46.3822,
  "averageAboveEma50Pct": 43.8723,
  "averageAboveEma200Pct": 37.5409,
  "recentSnapshots": [
    {
      "timestamp": "2026-07-04T00:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 100.0,
      "averageReturn24hPct": 4.5853,
      "medianReturn24hPct": 3.7954,
      "aboveEma50Pct": 100.0,
      "aboveEma200Pct": 96.4286
    },
    {
      "timestamp": "2026-07-04T01:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 96.4286,
      "averageReturn24hPct": 2.7329,
      "medianReturn24hPct": 2.1011,
      "aboveEma50Pct": 92.8571,
      "aboveEma200Pct": 96.4286
    },
    {
      "timestamp": "2026-07-04T02:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 96.4286,
      "averageReturn24hPct": 3.134,
      "medianReturn24hPct": 2.515,
      "aboveEma50Pct": 96.4286,
      "aboveEma200Pct": 96.4286
    },
    {
      "timestamp": "2026-07-04T03:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 96.4286,
      "averageReturn24hPct": 3.5864,
      "medianReturn24hPct": 3.0085,
      "aboveEma50Pct": 96.4286,
      "aboveEma200Pct": 100.0
    },
    {
      "timestamp": "2026-07-04T04:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 100.0,
      "averageReturn24hPct": 4.1561,
      "medianReturn24hPct": 3.4078,
      "aboveEma50Pct": 96.4286,
      "aboveEma200Pct": 96.4286
    },
    {
      "timestamp": "2026-07-04T05:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 100.0,
      "averageReturn24hPct": 3.1781,
      "medianReturn24hPct": 2.5694,
      "aboveEma50Pct": 96.4286,
      "aboveEma200Pct": 92.8571
    },
    {
      "timestamp": "2026-07-04T06:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 92.8571,
      "averageReturn24hPct": 2.463,
      "medianReturn24hPct": 1.974,
      "aboveEma50Pct": 92.8571,
      "aboveEma200Pct": 92.8571
    },
    {
      "timestamp": "2026-07-04T07:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 89.2857,
      "averageReturn24hPct": 2.1617,
      "medianReturn24hPct": 1.8134,
      "aboveEma50Pct": 96.4286,
      "aboveEma200Pct": 92.8571
    },
    {
      "timestamp": "2026-07-04T08:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 92.8571,
      "averageReturn24hPct": 2.13,
      "medianReturn24hPct": 1.6999,
      "aboveEma50Pct": 92.8571,
      "aboveEma200Pct": 92.8571
    },
    {
      "timestamp": "2026-07-04T09:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 71.4286,
      "averageReturn24hPct": 1.2394,
      "medianReturn24hPct": 1.0092,
      "aboveEma50Pct": 71.4286,
      "aboveEma200Pct": 89.2857
    },
    {
      "timestamp": "2026-07-04T10:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 64.2857,
      "averageReturn24hPct": 0.8775,
      "medianReturn24hPct": 0.6294,
      "aboveEma50Pct": 89.2857,
      "aboveEma200Pct": 92.8571
    },
    {
      "timestamp": "2026-07-04T11:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 60.7143,
      "averageReturn24hPct": 0.5715,
      "medianReturn24hPct": 0.4007,
      "aboveEma50Pct": 85.7143,
      "aboveEma200Pct": 96.4286
    },
    {
      "timestamp": "2026-07-04T12:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 67.8571,
      "averageReturn24hPct": 0.7792,
      "medianReturn24hPct": 0.5209,
      "aboveEma50Pct": 96.4286,
      "aboveEma200Pct": 96.4286
    },
    {
      "timestamp": "2026-07-04T13:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 60.7143,
      "averageReturn24hPct": 0.2635,
      "medianReturn24hPct": 0.4664,
      "aboveEma50Pct": 89.2857,
      "aboveEma200Pct": 92.8571
    },
    {
      "timestamp": "2026-07-04T14:00:00+00:00",
      "pairCount": 28,
      "positiveReturn24hPct": 71.4286,
      "averageReturn24hPct": 0.9034,
      "medianReturn24hPct": 0.7529,
      "aboveEma50Pct": 96.4286,
      "aboveEma200Pct": 96.4286
    },
    {
      "timestamp": "2026-07-04T15:00:00+00:00",
      "pairCount": 3,
      "positiveReturn24hPct": 100.0,
      "averageReturn24hPct": 2.1228,
      "medianReturn24hPct": 1.6263,
      "aboveEma50Pct": 100.0,
      "aboveEma200Pct": 100.0
    },
    {
      "timestamp": "2026-07-04T16:00:00+00:00",
      "pairCount": 3,
      "positiveReturn24hPct": 100.0,
      "averageReturn24hPct": 1.7408,
      "medianReturn24hPct": 1.3072,
      "aboveEma50Pct": 100.0,
      "aboveEma200Pct": 100.0
    },
    {
      "timestamp": "2026-07-04T17:00:00+00:00",
      "pairCount": 3,
      "positiveReturn24hPct": 100.0,
      "averageReturn24hPct": 2.0575,
      "medianReturn24hPct": 1.7307,
      "aboveEma50Pct": 100.0,
      "aboveEma200Pct": 100.0
    },
    {
      "timestamp": "2026-07-04T18:00:00+00:00",
      "pairCount": 3,
      "positiveReturn24hPct": 100.0,
      "averageReturn24hPct": 1.6266,
      "medianReturn24hPct": 1.5448,
      "aboveEma50Pct": 100.0,
      "aboveEma200Pct": 100.0
    },
    {
      "timestamp": "2026-07-04T19:00:00+00:00",
      "pairCount": 3,
      "positiveReturn24hPct": 66.6667,
      "averageReturn24hPct": 1.2437,
      "medianReturn24hPct": 1.756,
      "aboveEma50Pct": 100.0,
      "aboveEma200Pct": 100.0
    }
  ]
}

## Regime-Aware Failure Review

Conclusion:

Local OHLCV quality appears usable for research if warnings are reviewed, but the selected sample is strongly regime-sensitive. Recent long-only technical research failures are more consistent with adverse bear/high-volatility market context plus sparse validated alpha than with a single obvious data corruption issue.

Evidence:

- Data integrity status: warning with average missing rate 0.0%.
- BTC regime labels show bear/crash coverage around 33.557% and high-volatility coverage around 13.2398% in the selected local sample.
- V13.4.26 validated hypotheses: 6; top supported hypotheses: none.
- V13.4.23 benchmark dryRunApproved: False.
- V13.4.9 Trend Pullback dryRunApproved: False.
- V13.4.17 Dynamic Regime finalEntrySignals: unknown.

Limitations:

- Existing strategy and benchmark reports were not originally tagged per BTC regime, so this review maps them to sample-level market context rather than per-trade regime attribution.
- Breadth statistics use locally available 1h OHLCV as a proxy when exchange-wide historical membership is unavailable.
- No external market data was fetched for cross-validation; BTC sanity checks use local candles only.

Recommendations:

- Do not treat V13.4.26 failures as only a factor-quality issue until regime-tagged evaluations are available.
- Add regime labels to future backtest exports and factor validation samples before comparing strategy families.
- Require a no-trade or avoid regime for long-only technical strategies during crash/high-volatility bear samples.
- Run future V13.4.28 data expansion only after preserving this integrity review as the baseline.

## Safety Boundary

- dryRunApproved: False
- liveTradingApproved: False
- no strategy implementation
- no backtest execution
- no data download
- no Trade API
- no Withdraw API
- no real API key
- no account or position reads
- no order creation
- no auto trading
