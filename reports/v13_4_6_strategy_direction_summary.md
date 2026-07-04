# V13.4.6 Strategy Direction Summary

## Decision

- Volume Rebound V0.1/V0.2 current series is rejected for Dry-run.
- dryRunApproved: False
- strategyFamilyStatus: rejected_for_dry_run
- This is a strategy direction review only. It does not run backtests, enter Dry-run, or modify strategy code.

## Current V0.1/V0.2 Summary

- Best raw candidate in V13.4.5: AlphaPilotVolumeReboundV02CExitCleanup
- Best slippage-adjusted candidate in V13.4.5: AlphaPilotVolumeReboundV02CExitCleanup
- B/C/E were relative improvements in limited contexts, but absolute performance remains deeply negative.
- D was eliminated in V13.4.4 comparison and was not part of expanded validation.

### Raw Expanded Validation

| Strategy | Return % | Drawdown % | Profit Factor | Trades | Win Rate % |
|---|---:|---:|---:|---:|---:|
| AlphaPilotVolumeReboundV01 | -99.2732 | 99.3724 | 0.6689 | 2701 | 37.2825 |
| AlphaPilotVolumeReboundV02BVolumeQuality | -94.171 | 94.7185 | 0.6152 | 1515 | 36.9637 |
| AlphaPilotVolumeReboundV02CExitCleanup | -99.1303 | 99.2719 | 0.6739 | 2496 | 43.4295 |
| AlphaPilotVolumeReboundV02EPairRiskWatchlist | -99.3093 | 99.3953 | 0.6637 | 2671 | 37.0273 |

### Slippage-Adjusted Expanded Validation

| Strategy | Adj Return % | Adj DD % | Adj PF | Trades | Slippage Cost | Gate |
|---|---:|---:|---:|---:|---:|---|
| AlphaPilotVolumeReboundV01 | -193.4577 | 191.6168 | 0.4603 | 2701 | 941.84466739 | False |
| AlphaPilotVolumeReboundV02BVolumeQuality | -168.5489 | 165.9553 | 0.4225 | 1515 | 743.77896729 | False |
| AlphaPilotVolumeReboundV02CExitCleanup | -187.2377 | 182.3083 | 0.4726 | 2496 | 881.07407065 | True |
| AlphaPilotVolumeReboundV02EPairRiskWatchlist | -191.7425 | 190.0944 | 0.4569 | 2671 | 924.33185017 | False |

## Why Minor Tuning Should Stop

- Relative improvement is not strategy approval when absolute returns remain deeply negative.
- The current 15m rebound framework is highly cost-sensitive.
- A 1:1 payoff profile is weak when win rate is near the low-40% range and costs are material.
- The 4h trend filter blocks many weak contexts but is not sufficient by itself.
- Pair-level risk must be measured, capped, and reported instead of handled through permanent one-off exclusions.
- V03 should start from entry quality, trade frequency, payoff, and regime design rather than small threshold edits.

## Core Failure Reasons

### Trade Frequency

- V01, C, and E each produced roughly 2,500-2,700 trades on Top30 six-month validation.
- B reduced trades to 1,515 but remained deeply negative after slippage.
- 15m signal density appears noisy and likely amplifies fee/slippage drag.
- V03 should prefer fewer, higher-quality signals.

### Cost Sensitivity

- Every candidate became worse after slippage post-processing.
- The strategy family is cost-sensitive because trade count is high and edge per trade is weak.
- V03 must either reduce trade frequency, increase target expectancy, or both.

### Payoff Structure

- A roughly 1:1 payoff structure is not enough with win rate near the low-40% range.
- After fees and slippage, the strategy needs materially higher win rate or higher reward/risk.
- V03 should test at least 1.5R or 2R concepts before any controlled execution discussion.

### Entry Quality

- The volumeRatio, RSI, MACD, EMA20 reclaim, and broad 4h trend combination did not identify positive-expectancy entries.
- The expanded results suggest the failure is structural, not a single threshold issue.
- V03 should require stronger structure confirmation before entry.

### Trend Filter

- The 4h trend filter blocks many weak contexts and is useful as a guardrail.
- Passing the current 4h filter is not sufficient; trades that passed still lost overall.
- V03 should not rely on 4h EMA filtering alone.

### SOL / Pair Risk

- SOL contributed heavily to the smoke-sample loss, showing pair-level risk can drag the portfolio.
- A single smoke result is not enough to permanently exclude SOL.
- V03 should add pair-level exposure caps, signal caps, and risk watchlists.

## V03 Candidate Directions

### V03A - Trend Pullback Continuation

- Positioning: Trend pullback continuation strategy
- Core idea: Trade only in clearer bullish trend structures, wait for a pullback into a support or EMA zone, and require renewed strength confirmation before any historical backtest entry.
- Rule direction:
  - 4h trend is clearly up.
  - 1h structure remains intact.
  - 15m pulls back toward EMA20, EMA50, or a support area.
  - Price reclaims strength with volume confirmation.
  - Avoid weak-trend rebound attempts.
- Risks:
  - Signal count may become too low.
  - Late confirmation can miss early reversals.
  - Trend filters can still fail in regime shifts.

### V03B - Breakout Retest Confirmation

- Positioning: Breakout retest confirmation strategy
- Core idea: Avoid random rebounds and wait for a close above a meaningful resistance level, then require a retest that holds before historical backtest entry.
- Rule direction:
  - Identify a recent resistance zone.
  - Require 15m or 1h close above that zone.
  - Require retest without closing back below the breakout area.
  - Use volume confirmation and BTC environment safety.
  - Reject unconfirmed breakout candles.
- Risks:
  - False breakouts remain possible.
  - Retests may not appear.
  - The setup may be too sparse for some pairs.

### V03C - High Score Signal Only

- Positioning: Low-frequency high-quality signal strategy
- Core idea: Keep the volume rebound theme but require a transparent multi-factor score. Only high-score historical signals enter backtesting.
- Rule direction:
  - Score market safety, trend context, rebound location, volume quality, momentum improvement, and risk quality.
  - Require score >= 80 before any backtest entry.
  - Use pair-level exposure caps and daily signal limits.
  - Record score components in reports for auditability.
- Risks:
  - Scoring weights can overfit easily.
  - Signal count may become too low.
  - Manual score design needs careful validation.

### V03D - 1h Main Timeframe

- Positioning: Lower-noise 1h strategy direction
- Core idea: Move the primary signal timeframe from 15m to 1h to reduce noise, trade count, and cost sensitivity.
- Rule direction:
  - Use 1h candles as the main entry timeframe.
  - Use 4h market regime and trend filters.
  - Use 15m only for optional execution refinement in later versions.
  - Require wider targets or stronger risk/reward than 1:1.
- Risks:
  - Entries are slower.
  - Sample size is smaller.
  - Wider candles may require different stops and targets.

## V03 Quality Gate

- slippage-adjusted total return > 0
- slippage-adjusted profit factor > 1.15
- max drawdown materially below V0.1/V0.2 expanded validation
- max consecutive losses acceptable for the proposed risk model
- trade count sufficient for evidence but not excessive
- no single pair dominates profit or loss
- passes smoke validation and six-month Top30 validation
- preferably passes a longer timerange before any Dry-run discussion

## Do Not Proceed

- Do not enter Dry-run with V0.1/V0.2.
- Do not continue minor B/C/E threshold edits as the next step.
- Do not treat V02C relative improvement as usable performance.
- Do not run live trading.
- Do not add real API keys.
- Do not call Trade API or Withdraw API.
- Do not read real accounts or positions.
- Do not create real orders.
- Do not auto trade.

## Next Step

V13.4.7 - V03 Candidate Selection and Specification

## Safety

V13.4.6 reads local reports and writes research artifacts only. It does not modify V0.1/V0.2 strategy code, run backtests, enter Dry-run, use API keys, call Trade API or Withdraw API, read accounts, create orders, or auto trade.
