# V13.4.34 Candidate Implementation Plan

Recommended next version:

```text
V13.4.34 - Low-Frequency Candidate Implementation and Research Backtest
```

Scope:

- Pairs: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
- Timeframe: 4h
- Timerange: 20240101-

Implement first:

- `LF-CAND-A-4H-EMA-TREND-LONG`
- `LF-CAND-B-4H-BEAR-REJECTION-SHORT`
- `LF-CAND-E-NOTRADE-DEFENSIVE-REGIME`

Defer:

- `LF-CAND-C-1D-REGIME-4H-ENTRY-ROUTER`
- `LF-CAND-D-4H-BREAKOUT-RETEST`

Required reports:

- candidate comparison report
- baseline comparison
- long / short breakdown
- regime breakdown
- slippage-adjusted metrics
- `dryRunApproved=false`
- `liveTradingApproved=false`

Non-goals:

- no real API key
- no Trade API
- no Withdraw API
- no account reads
- no position reads
- no real orders
- no auto trading
