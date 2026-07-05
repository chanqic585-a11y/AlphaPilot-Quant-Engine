# AlphaPilot V13.4.26 Hypothesis Validation Summary

Status: research_only

V13.4.26 validates high-priority V13.4.25 research hypotheses against a rebuilt
FactorDataPanel and forward labels. It is research-only.

No strategy code was written. No Freqtrade backtest was run. No Dry-run or live
trading approval was granted.

## Core Counts

- hypothesisCount: 14
- validatedHypothesisCount: 6
- rejectedHypothesisCount: 4
- sampleCount: 124111

## Supported / Unsupported

- topSupportedHypotheses: none
- unsupportedHypotheses: HYP-001, HYP-002, HYP-004, HYP-006, HYP-007, HYP-008
- insufficientSampleHypotheses: none
- hypothesesWithPositiveExcessVsBTC: HYP-002

## Validation Metrics

- HYP-001 | Volatility as Risk Filter | no_support | pass=84151 | PF=0.87276618 | excessBTC=-0.00040943
- HYP-002 | Trend Strength as Regime Filter | no_support | pass=44315 | PF=0.96422343 | excessBTC=0.00038429
- HYP-004 | Bollinger Rebound Requires Regime Filter | no_support | pass=15917 | PF=0.8397104 | excessBTC=-0.00033335
- HYP-006 | Low Frequency Requirement | no_support | pass=4775 | PF=0.7677512 | excessBTC=-0.00064989
- HYP-007 | Liquidity Gate First | no_support | pass=50813 | PF=0.91744476 | excessBTC=-9.23e-05
- HYP-008 | BuyHoldBTC Benchmark Requirement | no_support | pass=123900 | PF=0.92159311 | excessBTC=-4.258e-05

## Stability Warnings

- HYP-001 not stable across months by the V13.4.26 research rule.
- HYP-002 not stable across months by the V13.4.26 research rule.
- HYP-004 not stable across months by the V13.4.26 research rule.
- HYP-006 not stable across months by the V13.4.26 research rule.
- HYP-007 not stable across months by the V13.4.26 research rule.
- HYP-008 not stable across months by the V13.4.26 research rule.

## Recommendations

- data_expansion: No high-priority hypothesis reached research support under V13.4.26 gates.
- safety_boundary: supportLevel is research evidence only; it is not a trading gate, Dry-run approval, order, or live trading permission.

## Next Step

V13.4.27 - Research Direction Reset / Data Expansion

## No-Lookahead Notes

- Condition features are point-in-time and use current or historical data only.
- Cross-sectional ranks are computed within the same timestamp only.
- Forward labels are forward-looking for validation only.
- Forward labels are not used to construct conditions, select pairs, modify universe membership, create orders, or approve Dry-run.
- BTC forward returns are used only for excess-return evaluation.

## Safety Boundary

- dryRunApproved: False
- liveTradingApproved: False
- no strategy implementation
- no backtest execution
- no Dry-run
- no Trade API
- no Withdraw API
- no API key
- no account or position reads
- no order creation
- no auto trading
