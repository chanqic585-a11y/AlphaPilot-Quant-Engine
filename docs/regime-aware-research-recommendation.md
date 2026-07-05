# Regime-Aware Research Recommendation

V13.4.27 recommends that future AlphaPilot research separates strategy quality
from market-regime exposure.

## Why

Prior V13.4 research showed that:

- V13.4.23 active benchmarks did not beat the no-trade or BTC baseline.
- V13.4.26 high-priority factor hypotheses had no directly supported
  candidates.
- Long-only technical ideas were fragile in the selected local sample.
- BTC regime labels show bear, sideways, crash, and high-volatility periods.

This suggests the issue is not only a strategy parameter problem. A strategy can
look weak because it is being evaluated inside an adverse market regime.

## Recommendation

Future reports should include:

- BTC regime label at sample time
- broad market breadth snapshot
- dynamic universe membership
- no-trade / avoid-regime accounting
- per-regime returns, drawdown, trade count, and profit factor
- separate analysis for bull, bear, sideways, crash, and recovery samples

## V13.4.28 Direction

The postponed data expansion should proceed only after keeping V13.4.27 as a
baseline integrity snapshot. Expansion should improve coverage but should not
overwrite or hide the current missing-file and regime warnings.

## Safety Boundary

This recommendation is research-only. It does not approve Dry-run, live
trading, exchange credentials, account reads, order creation, or auto trading.
