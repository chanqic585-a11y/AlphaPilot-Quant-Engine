# V13.5 Strategy Decision Summary

V13.5 does not approve a strategy for paper or Dry-run.

## Hard Gate

A strategy candidate must pass all of these gates:

- trade count >= 100
- win rate >= 55%
- reward/risk >= 1.8, target 2.0
- profit factor >= 1.35
- max drawdown <= 20%
- positive after estimated fees and slippage
- recent period must not collapse

## 4h Result

The best probability-gated 4h candidate produced only 28 trades. It was
profitable in sample, but the sample count was too small for paper testing.

The best deterministic 4h mined rule was ETH long continuation with neutral
mark basis. It had useful historical behavior, but failed the hard gate because
sample count was below 100, reward/risk was below the required level, and recent
robustness was not strong enough.

## 1h Result

The best 1h probability-gated candidate produced enough trades, but it did not
clear the 55% win-rate / 2R gate and had excessive drawdown.

The best deterministic 1h mined rule was SOL long continuation with low ATR. It
had enough trades and a win rate above 55%, but failed because reward/risk was
too low and drawdown was too high.

## Product Decision

Do not start paper trading or Dry-run from V13.5.

The useful output is the reusable pipeline:

- local derivatives feature panel
- triple-barrier labeling
- walk-forward probability gate
- deterministic rule mining
- hard-gate report

The next useful implementation should focus on better input data rather than
more OHLCV parameter tuning.
