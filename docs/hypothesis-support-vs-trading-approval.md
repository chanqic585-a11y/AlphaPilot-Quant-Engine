# Hypothesis Support vs Trading Approval

Hypothesis validation support is not trading approval.

## Research Support Means

Research support means a condition combination showed statistical evidence in a
historical validation dataset.

It may justify:

- more validation
- better data collection
- a research-only strategy specification
- benchmark comparison design

It does not justify:

- Dry-run
- live trading
- order creation
- API key use
- automatic trading

## V13.4.26 Result

No high-priority hypothesis reached support.

Therefore V13.4.26 does not recommend a hypothesis-based strategy
specification.

## Required Separation

Future versions must preserve this chain:

```text
hypothesis -> validation dataset -> research support -> strategy specification -> backtest -> review -> Dry-run review
```

Skipping steps would violate AlphaPilot's safety boundary.

## Safety Boundary

```text
supportLevel != dryRunApproved
supportLevel != liveTradingApproved
supportLevel != trading signal
supportLevel != order instruction
```
