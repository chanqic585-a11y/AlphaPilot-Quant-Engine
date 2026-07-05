# Short Strategy Risk Notes

Short strategies can fail quickly when rebound behavior is misread, volatility
expands, or the strategy enters too frequently. V13.4.29 demonstrates this
risk clearly.

## V13.4.29 Risk Findings

Expanded result:

```text
tradeCount: 5052
totalReturnPct: -99.9966
maxDrawdownPct: 99.9966
profitFactor: 0.782
slippageAdjustedProfitFactor: 0.5966
maxConsecutiveLosses: 77
```

Dominant loss driver:

```text
stop_loss exits: 3532
stop_loss profit_total_pct: -456.78
```

This means the first simple short-score design is too noisy and should not be
continued as-is.

## Required Boundary

V13.4.29 does not approve:

- Dry-run
- live trading
- real API keys
- Trade API
- Withdraw API
- account reads
- position reads
- order creation
- auto trading

## Recommended Handling

Archive this strategy as a failed benchmark unless a future review identifies a
specific structural fix. Do not keep adding filters blindly just to make the
result look better.
