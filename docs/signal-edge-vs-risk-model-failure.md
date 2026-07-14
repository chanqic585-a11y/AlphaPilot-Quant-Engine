# Signal Edge vs Risk Model Failure

AlphaPilot evaluates two layers independently.

## Signal layer

The signal layer asks whether entries and exits produced positive evidence:

- Profit factor at or above 1.
- Positive total return on the observed sample.
- Positive average net R when available.
- Trade frequency consistent with a plausible edge rather than repeated noise.

A failed signal layer cannot be repaired by leverage, larger position size, or
looser drawdown limits.

## Account and risk layer

The account/risk layer asks whether the path was survivable:

- Maximum drawdown.
- Maximum consecutive losses.
- Cost and slippage stress.
- Pair and time concentration.
- Exposure and exit behavior when available.

A tolerable drawdown does not prove a signal edge. Likewise, a positive raw
signal does not pass if the account path fails after costs and risk limits.

## Classification boundary

The generated attribution reports both assessments and sets
`causalityProven=false`. It never hides one layer behind a combined headline
score.
