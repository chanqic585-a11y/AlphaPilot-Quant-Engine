# Strategy Research Factory

The Strategy Research Factory is the design bridge between factor research and
future strategy candidates.

It exists to stop AlphaPilot from writing strategies before factor evidence is
measured.

## Workflow

```text
1. Generate candidate factors.
2. Evaluate factors.
3. Filter stable factors.
4. Combine factors into strategy hypotheses.
5. Compare hypotheses against the Benchmark Strategy Suite.
6. Implement Freqtrade strategy only after research passes.
7. Run smoke and expanded validation.
8. Keep Dry-run approval as a separate review.
```

## Dynamic Regime Integration

The factory should consume:

- historical dynamic universe snapshots
- regime labels
- factor data panel rows
- factor evaluation reports
- benchmark comparison reports

It may output future dynamic regime strategy candidates, but that output is not
a trading gate and not an order instruction.

## Audit Requirements

Every future strategy hypothesis should record:

- source factor IDs
- data coverage
- missing-rate caveats
- benchmark comparison
- rejected hypotheses
- safety boundary before implementation
