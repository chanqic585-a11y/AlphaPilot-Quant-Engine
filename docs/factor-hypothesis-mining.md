# Factor Hypothesis Mining

Factor hypothesis mining is the research-only step between factor evaluation and
future strategy implementation.

It answers:

```text
Which research ideas are worth validating next?
Which ideas are already rejected?
Which evidence supports each idea?
Which benchmarks must a future candidate beat?
```

It does not answer:

```text
Which strategy should trade?
Which pair should be bought?
Should Dry-run start?
Should live trading start?
```

## Input Evidence

V13.4.25 uses three evidence groups:

1. Factor evidence from V13.4.22.
2. Benchmark behavior from V13.4.23.
3. Failure attribution and reset guidance from V13.4.24.

## Hypothesis Categories

```text
factor_based
benchmark_informed
regime_based
execution_reality
rejected
```

## Required Hypothesis Fields

Every hypothesis records:

- hypothesisId
- name
- category
- status
- evidence
- sourceReports
- proposedMechanism
- expectedBehavior
- riskNotes
- requiredData
- validationPlan
- invalidationRules
- priority
- dryRunApproved
- liveTradingApproved

All hypotheses keep:

```text
dryRunApproved: false
liveTradingApproved: false
```

## Main Mining Results

Volatility, ATR, trend strength, EMA50 distance, Bollinger position, and volume
expansion are not promoted into entry rules. They become research context for
future validation datasets.

The benchmark review adds hard constraints:

- low frequency must be studied before strategy implementation
- liquidity and execution feasibility must be checked first
- NoTrade and BuyHoldBTC comparisons are mandatory
- BenchmarkBollingerRebound is only a reference, not a usable strategy

## Validation Standard

A future hypothesis can only move forward if it shows:

- enough sample coverage
- cost-adjusted improvement versus NoTrade and BuyHoldBTC
- pair and month stability
- clear execution-reality notes
- explicit invalidation rules

This is still not Dry-run approval.

## V13.4.26 Follow-Up

V13.4.26 validated the high-priority hypotheses from this registry. None reached
weak, moderate, or strong research support under the current gates.

The research factory therefore should not move into strategy implementation
yet. The next step is research direction reset or data expansion.
