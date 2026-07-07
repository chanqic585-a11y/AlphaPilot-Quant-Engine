# AlphaPilot V13.7.21 Paper Observation Task Pack

This report turns V13.7.20 research candidates into local paper-observation tasks.
It is not exchange Dry-run, not live trading, not an order system, and not trading advice.

## Summary

- status: completed
- taskCount: 5
- plannedPaperObservationCount: 5
- standardConfidenceCount: 2
- cautiousObservationCount: 3
- targetClosedSamplesTotal: 130
- dryRunApproved: False
- liveTradingApproved: False

## Observation Tasks

| Rank | Task | Tier | Days | Target Samples | Historical Trades | PF | Win % | DD % |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1D 趋势突破确认 ATR2.0 | medium_caution | 90 | 25 | 319 | 1.5035 | 45.4545 | 21.4697 |
| 2 | 1D 横盘超卖修复 ATR1.2 | medium_caution | 90 | 25 | 36 | 2.4289 | 58.3333 | 6.8439 |
| 3 | 1D 横盘超卖修复 ATR1.0 | cautious | 120 | 30 | 38 | 2.2125 | 55.2632 | 7.7808 |
| 4 | 1D 趋势低波突破 ATR2.0 | standard | 60 | 25 | 207 | 1.3856 | 43.4783 | 20.0035 |
| 5 | 1D 广谱低波突破 ATR2.0 | standard | 60 | 25 | 220 | 1.3152 | 42.2727 | 20.8539 |

### 1D 趋势突破确认 ATR2.0

Weak points:
- test_2025_2026 profit factor is close to break-even: 1.0028.
- test_2025_2026 return is thin: 0.0842%.
- Historical max consecutive losses reached 12.

Promotion criteria:
- Collect at least 25 closed local paper-observation samples.
- Forward paper-observation profit factor must remain above 1.20.
- Forward paper-observation average R must remain positive.
- Max drawdown must stay within the historical drawdown plus a documented tolerance.
- No unreviewed regime drift, liquidity issue, or data-quality issue may remain open.

Rejection criteria:
- Reject or redesign if forward paper-observation PF is below 1.0 after the target sample count.
- Reject or redesign if three or more severe data-quality or liquidity warnings appear.
- Reject or redesign if observed signals concentrate in pairs that were historically weak.
- Reject or redesign if the rule requires discretionary exceptions to look acceptable.

### 1D 横盘超卖修复 ATR1.2

Weak points:
- train_2020_2022 sample is thin: 4 trades.

Promotion criteria:
- Collect at least 25 closed local paper-observation samples.
- Forward paper-observation profit factor must remain above 1.20.
- Forward paper-observation average R must remain positive.
- Max drawdown must stay within the historical drawdown plus a documented tolerance.
- No unreviewed regime drift, liquidity issue, or data-quality issue may remain open.

Rejection criteria:
- Reject or redesign if forward paper-observation PF is below 1.0 after the target sample count.
- Reject or redesign if three or more severe data-quality or liquidity warnings appear.
- Reject or redesign if observed signals concentrate in pairs that were historically weak.
- Reject or redesign if the rule requires discretionary exceptions to look acceptable.

### 1D 横盘超卖修复 ATR1.0

Weak points:
- train_2020_2022 sample is thin: 4 trades.
- validation_2023_2024 profit factor is close to break-even: 1.0465.
- validation_2023_2024 return is thin: 0.382%.

Promotion criteria:
- Collect at least 30 closed local paper-observation samples.
- Forward paper-observation profit factor must remain above 1.20.
- Forward paper-observation average R must remain positive.
- Max drawdown must stay within the historical drawdown plus a documented tolerance.
- No unreviewed regime drift, liquidity issue, or data-quality issue may remain open.

Rejection criteria:
- Reject or redesign if forward paper-observation PF is below 1.0 after the target sample count.
- Reject or redesign if three or more severe data-quality or liquidity warnings appear.
- Reject or redesign if observed signals concentrate in pairs that were historically weak.
- Reject or redesign if the rule requires discretionary exceptions to look acceptable.

### 1D 趋势低波突破 ATR2.0

Weak points:
- Historical max consecutive losses reached 10.

Promotion criteria:
- Collect at least 25 closed local paper-observation samples.
- Forward paper-observation profit factor must remain above 1.20.
- Forward paper-observation average R must remain positive.
- Max drawdown must stay within the historical drawdown plus a documented tolerance.
- No unreviewed regime drift, liquidity issue, or data-quality issue may remain open.

Rejection criteria:
- Reject or redesign if forward paper-observation PF is below 1.0 after the target sample count.
- Reject or redesign if three or more severe data-quality or liquidity warnings appear.
- Reject or redesign if observed signals concentrate in pairs that were historically weak.
- Reject or redesign if the rule requires discretionary exceptions to look acceptable.

### 1D 广谱低波突破 ATR2.0

Weak points:
- Historical max consecutive losses reached 11.

Promotion criteria:
- Collect at least 25 closed local paper-observation samples.
- Forward paper-observation profit factor must remain above 1.20.
- Forward paper-observation average R must remain positive.
- Max drawdown must stay within the historical drawdown plus a documented tolerance.
- No unreviewed regime drift, liquidity issue, or data-quality issue may remain open.

Rejection criteria:
- Reject or redesign if forward paper-observation PF is below 1.0 after the target sample count.
- Reject or redesign if three or more severe data-quality or liquidity warnings appear.
- Reject or redesign if observed signals concentrate in pairs that were historically weak.
- Reject or redesign if the rule requires discretionary exceptions to look acceptable.

## Safety Boundary

- realTradingEnabled: False
- exchangeDryRunApproved: False
- liveTradingApproved: False
- tradeApiEnabled: False
- withdrawApiEnabled: False
- apiKeyStorage: False
- realAccountReads: False
- realPositionReads: False
- orderCreation: False
- autoTrading: False

## Next Step

Use the desktop console to track these local paper-observation tasks; do not move to exchange Dry-run.
