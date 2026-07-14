# Failure Attribution Methodology

## Evidence order

1. Raw local backtest artifact.
2. Structured JSON report.
3. Markdown summary.
4. Strategy code or prompt only.

Higher-level evidence can support stronger observations, but no evidence level
alone grants promotion. Missing values remain `null` and are listed under
`missingEvidenceFields`.

## Normalized metrics

The matrix preserves trade count, raw and slippage-adjusted return, win rate,
raw and adjusted profit factor, drawdown, consecutive losses, holding time,
fees, slippage cost, average net R, gross reward/risk, pair count, and month
count when available.

## Attribution order

1. Reject prohibited risk designs such as Martingale.
2. Identify missing core evidence.
3. Evaluate signal edge from profit factor, return, and average net R.
4. Evaluate account-path risk from drawdown and loss sequences.
5. Add cost, frequency, pair, exit, direction/regime, data, and runtime
   weaknesses as secondary labels.

The output deliberately allows multiple secondary failures. A high trade count
may amplify a weak edge through costs, while a high drawdown may reveal a
separate portfolio/risk-model failure.

## Limits

- Existing reports cover different samples and do not all expose trade rows.
- Pair, month, exit, and regime attribution is only emitted when evidence is
  present.
- Recurring patterns are associations, not causal proof.
- This report does not compare newly tuned variants and therefore cannot make
  a strategy promotion decision.
