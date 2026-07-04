# Research Gate vs Trading Gate Boundary

AlphaPilot separates research gates from trading gates.

## Research Gate

A research gate can be used to answer:

- Which historical contexts deserve further study?
- Which probability buckets have enough coverage for a backtest candidate?
- Which candidate should be compared in the next controlled validation?

A research gate may write reports, configs, and docs. It may not create orders,
start Dry-run, or enable live execution.

## Trading Gate

A trading gate would require a different approval path. It must evaluate:

- backtest robustness
- out-of-sample behavior
- slippage and fees
- liquidity and market impact
- drawdown and risk caps
- operational safety
- manual approval boundaries
- exchange permission isolation

V13.4.20 does not implement a trading gate.

## V13.4.20 Boundary

The V13.4.20 candidate configs are research artifacts only:

- no real API key
- no Trade API
- no Withdraw API
- no account balance read
- no position read
- no real order
- no auto trading
- no Dry-run approval

The next permitted action is a V13.4.21 comparative research backtest.
