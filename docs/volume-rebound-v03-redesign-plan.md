# Volume Rebound V03 Redesign Plan

V03 must be a strategy redesign, not a small parameter change on V0.1/V0.2.

## Design Principles

V03 should redesign:

- entry quality
- trade frequency
- reward/risk
- trend structure
- pair-level exposure
- cost sensitivity
- market regime
- signal confirmation

## Candidate Directions

### V03A - Trend Pullback Continuation

Only trade in clearer bullish trend structures. Wait for price to pull back into
an EMA or support area, then require renewed strength confirmation.

This direction should reduce weak-trend rebound attempts and avoid catching
falling moves, but it may produce fewer signals and miss early reversals.

### V03B - Breakout Retest Confirmation

Wait for price to break above meaningful resistance, then require a retest that
holds before historical backtest entry.

This direction is more structurally explainable than random rebound entries, but
false breakouts and missing retests remain risks.

### V03C - High Score Signal Only

Keep the volume rebound theme, but require a transparent multi-factor score.
Only high-score signals enter backtesting.

Suggested factors:

- market safety
- trend environment
- rebound location
- volume quality
- momentum improvement
- risk quality

The first research threshold should be `score >= 80`.

### V03D - 1h Main Timeframe

Move the main signal timeframe from 15m to 1h to reduce noise and cost
sensitivity. Use 4h for regime context and reserve 15m only for optional later
execution refinement.

## Quality Gate

Before any Dry-run discussion, V03 must satisfy:

- slippage-adjusted total return > 0
- slippage-adjusted profit factor > 1.15
- max drawdown materially below V0.1/V0.2 expanded validation
- acceptable max consecutive losses
- sufficient but not excessive trade count
- no single pair extreme dominance
- smoke and six-month Top30 validation both pass
- preferably longer timerange validation also passes

Stricter target:

```text
profit factor >= 1.2
max drawdown < 25%
slippage-adjusted total return > 0
```

If these gates are not met, V03 must not enter Dry-run.

## Next Step

Recommended next version:

```text
V13.4.7 - V03 Candidate Selection and Specification
```

That version should select one V03 direction, define exact strategy rules, and
prepare a backtest plan. It should not enter Dry-run.

