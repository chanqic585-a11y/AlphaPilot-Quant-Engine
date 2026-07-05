# Hypothesis Validation Methodology

V13.4.26 converts high-priority research hypotheses into point-in-time
condition rules, then evaluates those conditions with forward labels.

## Validated Hypotheses

- HYP-001 Volatility as Risk Filter
- HYP-002 Trend Strength as Regime Filter
- HYP-004 Bollinger Rebound Requires Regime Filter
- HYP-006 Low Frequency Requirement
- HYP-007 Liquidity Gate First
- HYP-008 BuyHoldBTC Benchmark Requirement

Rejected hypotheses are retained in reports but are not validated.

## Condition Rules

Rules are implemented in:

```text
alphapilot/research_factory/hypothesis_validation_rules.py
```

Each rule records:

- hypothesisId
- conditionId
- description
- requiredColumns
- noLookaheadNotes

## Metrics

Each hypothesis receives:

- sampleCount
- conditionPassCount
- conditionPassRate
- validLabelCount
- averageForwardReturn
- medianForwardReturn
- TP-first probability
- SL-first probability
- profitFactor
- expectancy
- average MFE
- average MAE
- average excess return versus BTC
- monthly stability
- pair stability
- regime stability
- liquidity stability

## Support Levels

```text
strong_research_support
moderate_research_support
weak_research_support
no_support
insufficient_sample
```

The support gates are research gates only. They do not approve Dry-run or live
trading.

## V13.4.26 Result

No hypothesis reached weak, moderate, or strong research support.

This result prevents premature strategy implementation and pushes the next step
toward research reset or data expansion.
