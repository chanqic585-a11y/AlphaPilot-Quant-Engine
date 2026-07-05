# V13.5.11 Cross-Market Public Data Smoke Report

This report verifies public daily OHLCV access across A-share, Hong Kong, US ETF, and index samples.
It is research-only and does not create trading signals or execution permissions.

## Summary

- Status: `completed`
- Symbol count: `8`
- Success count: `8`
- Failure count: `0`
- Total rows: `4928`
- Markets: `cn_a_share, hk_stock, index, us_etf`
- Range: `2024-01-01 -> 2026-07-06`
- Interval: `1d`

## Symbol Quality

- `600519.SS` (cn_a_share, Kweichow Moutai)
  - status: `ok`
  - rows: `604`
  - date range: `2024-01-02 -> 2026-07-03`
  - quality: `100`
  - daily volatility: `1.487094`
  - max drawdown: `33.975706`
- `000001.SZ` (cn_a_share, Ping An Bank)
  - status: `ok`
  - rows: `604`
  - date range: `2024-01-02 -> 2026-07-03`
  - quality: `100`
  - daily volatility: `1.317986`
  - max drawdown: `23.748104`
- `0700.HK` (hk_stock, Tencent)
  - status: `ok`
  - rows: `613`
  - date range: `2024-01-02 -> 2026-07-03`
  - quality: `100`
  - daily volatility: `2.012586`
  - max drawdown: `39.217714`
- `9988.HK` (hk_stock, Alibaba HK)
  - status: `ok`
  - rows: `613`
  - date range: `2024-01-02 -> 2026-07-03`
  - quality: `100`
  - daily volatility: `2.873082`
  - max drawdown: `51.64776`
- `SPY` (us_etf, SPDR S&P 500 ETF)
  - status: `ok`
  - rows: `627`
  - date range: `2024-01-02 -> 2026-07-02`
  - quality: `100`
  - daily volatility: `1.003774`
  - max drawdown: `18.998904`
- `QQQ` (us_etf, Invesco QQQ ETF)
  - status: `ok`
  - rows: `627`
  - date range: `2024-01-02 -> 2026-07-02`
  - quality: `100`
  - daily volatility: `1.32159`
  - max drawdown: `22.883307`
- `^HSI` (index, Hang Seng Index)
  - status: `ok`
  - rows: `613`
  - date range: `2024-01-02 -> 2026-07-03`
  - quality: `100`
  - daily volatility: `1.502259`
  - max drawdown: `19.954026`
- `^GSPC` (index, S&P 500 Index)
  - status: `ok`
  - rows: `627`
  - date range: `2024-01-02 -> 2026-07-02`
  - quality: `100`
  - daily volatility: `0.98241`
  - max drawdown: `18.902206`

## Integration Boundary

- Cross-market samples are research references only.
- A-share, Hong Kong, US ETF, and index samples must stay explicitly labeled.
- These samples are not crypto trade commands.
- Raw cache files are local-only and are not committed to Git.
- Data source terms must be reviewed before production redistribution.

## Safety Boundary

- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No real orders.
- No exchange Dry-run approval.
- No live trading approval.
- No automatic trading.
