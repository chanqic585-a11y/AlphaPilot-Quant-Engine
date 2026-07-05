# AlphaPilot V13.4.33 Low-Frequency Candidate Specification

V13.4.33 converts the V13.4.32 low-frequency baselines into explicit candidate specs and baseline hurdles. It is spec-only: no strategy implementation, no backtest, no Dry-run, and no live trading approval.

## Status

- currentStatus: spec_only
- sourceBaselineReport: reports/v13_4_32_low_frequency_baseline_report.json
- dryRunApproved: False
- liveTradingApproved: False

## Universal Hurdles

- dryRunApproved: False
- liveTradingApproved: False
- mustBeatNoTrade: True
- mustReportVsBuyHold: True
- mustReportVsEqualWeight: True
- mustReportRegimeBreakdown: True
- mustReportLongShortBreakdown: True
- mustReportSlippageAdjustedMetrics: True

## Candidates

### LF-CAND-A-4H-EMA-TREND-LONG - 4H EMA Trend Long

- direction: long
- timeframe: 4h
- status: spec_only
- coreConditions:
  - 4h close > EMA200
  - 4h EMA20 > EMA50
  - close pullback near EMA20 or EMA50
  - close reclaims EMA20
  - volume not collapsing
- validationPlan:
  - Implement only after V13.4.33 approval.
  - Backtest BTC/ETH/SOL 4h from 20240101-.
  - Report long-only results vs NoTrade, pair BuyHold, and EqualWeight.
  - Report regime and slippage-adjusted breakdown.

### LF-CAND-B-4H-BEAR-REJECTION-SHORT - 4H Bear Rejection Short

- direction: short
- timeframe: 4h
- status: spec_only
- coreConditions:
  - 4h price rejects EMA20 or EMA50 area
  - close falls back below EMA20
  - MACD histogram weakens
  - RSI below 55 or falling
  - no chase after large drop
- validationPlan:
  - Implement after Candidate A or alongside it in V13.4.34 only.
  - Backtest as short-only on BTC/ETH/SOL 4h from 20240101-.
  - Report vs NoTrade, pair BuyHold opportunity cost, and EqualWeight.
  - Report bear/recovery/sideways/crash exposure and no-chase failures.

### LF-CAND-C-1D-REGIME-4H-ENTRY-ROUTER - 1D Regime + 4H Entry Directional Router

- direction: long_or_short
- timeframe: 1d regime + 4h entry
- status: spec_only
- coreConditions:
  - 1d regime gives directional bias
  - 4h confirms direction
  - avoidScore not high
  - longScore or shortScore exceeds threshold
  - entry not extended
- validationPlan:
  - Keep V13.4.34 report-only unless Candidate A/B are stable.
  - Compare routed decisions against non-routed Candidate A/B.
  - Report noTradeRatio by regime.

### LF-CAND-D-4H-BREAKOUT-RETEST - 4H Breakout / Breakdown Retest

- direction: long_or_short
- timeframe: 4h
- status: spec_only
- coreConditions:
  - break recent N-bar high or low
  - retest confirms the breakout or breakdown level
  - volume not collapsing
  - close resumes in the breakout or breakdown direction
- validationPlan:
  - Defer executable implementation until Candidate A/B are evaluated.
  - First validate N-bar level definitions in a report-only sample.
  - Then compare long and short branches separately.

### LF-CAND-E-NOTRADE-DEFENSIVE-REGIME - NoTrade as Active Decision

- direction: no_trade_filter
- timeframe: 1d / 4h
- status: research_only
- coreConditions:
  - crash/high-volatility regime
  - direction scores conflict
  - liquidity or spread unavailable
  - extreme candle or data anomaly
- validationPlan:
  - Evaluate as overlay on Candidate A and B in V13.4.34.
  - Report no-trade opportunity cost versus BuyHold and EqualWeight.
  - Do not allow it to hide poor candidate definitions.

## Directional Score Framework

- status: research_only
- scoreRange: 0-5
- longScoreInputs: trend up, pullback quality, reclaim of EMA20 or EMA50, volume health, regime supportive
- shortScoreInputs: trend down or rejection, failed bounce, momentum weakening, no chase after large drop, regime supportive
- avoidScoreInputs: crash or extreme volatility, technical direction conflict, data quality issue, liquidity or spread unavailable, entry extended beyond risk concept

## V13.4.34 Plan

- name: Low-Frequency Candidate Implementation and Research Backtest
- timerange: 20240101-
- candidatesToImplement:
  - LF-CAND-A-4H-EMA-TREND-LONG
  - LF-CAND-B-4H-BEAR-REJECTION-SHORT
  - LF-CAND-E-NOTRADE-DEFENSIVE-REGIME

## Safety Boundary

- strategyImplemented: False
- backtestExecuted: False
- dataDownloaded: False
- dryRunApproved: False
- liveTradingApproved: False
- tradeApiUsed: False
- withdrawApiUsed: False
- apiKeyStored: False
- accountRead: False
- positionRead: False
- orderCreated: False
- autoTradingUsed: False
- mobileAppModified: False
