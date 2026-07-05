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

## V13.4.25 Hypothesis Mining

V13.4.25 turns the factory design into a research-only hypothesis registry.

Inputs:

- V13.4.22 factor evaluation
- V13.4.23 benchmark suite
- V13.4.24 benchmark result review

Outputs:

- `reports/v13_4_25_strategy_research_factory_report.json`
- `reports/v13_4_25_strategy_research_factory_summary.md`
- `reports/v13_4_25_research_hypotheses.json`

The registry includes factor-based, benchmark-informed, regime-based,
execution-reality, and rejected hypotheses. It does not write strategy code and
does not approve Dry-run or live trading.

The next step is V13.4.26, which should build a validation dataset for the
highest-priority hypotheses before any strategy implementation.
