# Probability Gate Coverage Diagnosis

V13.4.18 inspects the V13.4.14 probability score table and the V13.4.17
expanded validation funnel.

## Diagnosis Boundary

This document does not propose immediate trading, Dry-run, or live execution.
It only explains why the current research pipeline produced zero final entries.

## Current Gate

The current probability gate effectively requires:

```text
sampleCount >= 50
hitTpBeforeSlProbability >= 0.45
profitFactor >= 1.2
expectancy > 0
decision = research_candidate
```

V13.4.14 produced many bucket combinations with insufficient sample count and no
current-gate pass buckets. V13.4.17 still found probability lookup hits, but no
rows passed the score gate.

Observed counts:

```text
scoreTableBuckets: 283
sufficientSampleBuckets: 2
insufficientSampleBuckets: 281
researchCandidateBuckets: 0
currentGatePassBuckets: 0
probabilityLookupHits: 62352
probabilityScorePass: 0
```

## Interpretation

The immediate blocker is not that the strategy cannot produce candidates. It
can. The blocker is that the statistical gate has no sufficiently supported
`research_candidate` buckets for the expanded validation context.

## Recommended Fix Direction

The next research step should coarsen bucket dimensions and expand sample
coverage before any new backtest approval decision. Do not change live trading
permissions or enter Dry-run based on this diagnosis.

## V13.4.19 Follow-up

V13.4.19 performed bucket-level coarsening from the existing V13.4.14 score
table. Broad schemes C and D produced research buckets, but no scheme produced a
current-gate pass bucket. This supports the conclusion that the original table
is too sparse while also preserving the trading boundary: coarsened buckets are
research candidates only.
