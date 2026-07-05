# No-Lookahead Hypothesis Validation

V13.4.26 separates point-in-time features from forward-looking validation
labels.

## Allowed For Conditions

Conditions may use:

- current candle OHLCV-derived factors
- rolling features based on current and historical candles
- cross-sectional ranks at the same timestamp
- current regime labels
- current universe membership
- current liquidity and volatility buckets

## Not Allowed For Conditions

Conditions must not use:

- future returns
- future MFE / MAE
- TP / SL hit labels
- future BTC return
- future pair performance
- future universe membership
- future benchmark outcome

## Forward Labels

Forward labels are allowed only for evaluation:

- `forwardReturn_4/8/12/24`
- `mfePct_4/8/12/24`
- `maePct_4/8/12/24`
- `hitTpBeforeSl_4/8/12/24`
- `hitSlBeforeTp_4/8/12/24`
- `btcForwardReturn_4/8/12/24`
- `excessReturnVsBTC_4/8/12/24`

They never feed back into condition construction.

## V13.4.26 Assurance

The report records:

```text
features are point-in-time
labels are forward-looking for validation only
```

This keeps hypothesis validation separate from strategy execution and prevents
lookahead leakage.
