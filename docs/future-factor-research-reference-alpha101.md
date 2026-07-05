# Future Factor Research Reference: yydhYYDH/alpha101

Status: reference-only
Source repo: https://github.com/yydhYYDH/alpha101
Source license: unknown from raw LICENSE fetch on 2026-07-06
Recorded at: 2026-07-06

This document records alpha101 concepts that are useful for future AlphaPilot
factor research. It does not copy source code, does not import the project, and
does not create trading signals or orders.

## Source Metadata

| Field | Value |
|---|---|
| Repository | `yydhYYDH/alpha101` |
| URL | https://github.com/yydhYYDH/alpha101 |
| License | Unknown from raw LICENSE fetch on 2026-07-06 |
| Summary | Crypto factor research toolkit with Alpha101-style expressions, factor panels, expression evaluation, factor search, backtesting, and Freqtrade-based public kline ingestion. |
| Citation | GitHub README and repository metadata viewed on 2026-07-06. |

Only URL, license, summary, and citation-style metadata are stored here. Do not
copy large source passages into AlphaPilot.

## Concepts To Preserve For Future AlphaPilot Work

### 1. Wide Factor Panel

Reference concept:

- organize OHLCV and derived fields into time-by-symbol panels
- support cross-sectional and time-series factor operations
- keep data source and universe definition explicit

AlphaPilot future use:

- standardize a local factor panel around public OHLCV, funding, mark basis,
  liquidity proxies, and regime labels
- preserve pair/timeframe coverage metadata
- avoid mixing data-source expansion with strategy approval in the same gate

### 2. Alpha-Style Expression Language

Reference concept:

- expression-based factors such as ranks, rolling ranks, correlations, decay,
  z-scores, and conditional expressions
- safe expression evaluation against known fields/operators

AlphaPilot future use:

- build a small allowlisted factor grammar before any genetic search
- keep every factor as a research artifact with metadata
- record formula, inputs, data coverage, and evaluation window
- reject expressions that need unavailable or fabricated fields

### 3. Factor Search

Reference concept:

- search candidate expressions over a field/operator grammar
- evaluate each generation using forward-return metrics
- save search outputs and summaries

AlphaPilot future use:

- run search offline only
- separate train/search window from validation window
- require out-of-sample and recent-window checks
- store rejected candidates for later review
- do not convert search output directly into live orders

### 4. Factor Evaluation

Reference concept:

- evaluate factors with IC-style statistics, return metrics, Sharpe-like
  measures, and drawdown

AlphaPilot future use:

- add factor IC and rank-return reports alongside current win-rate/PF/RR
  metrics
- compare factors by regime and pair coverage
- track decay and recent stability
- require factor-level evidence before adding to strategy rules

### 5. Research Service / Visualization

Reference concept:

- a lightweight research interface for expression testing and result review

AlphaPilot future use:

- later add a read-only factor review dashboard
- show factor formula, data coverage, train/test split, regime breakdown, and
  why a factor is rejected or watchlisted
- keep it separate from execution controls

## Explicit Current Boundary

This reference document does not add:

- factor genetic search runtime
- new strategy approval
- Trade API
- Withdraw API
- exchange API keys
- real account reads
- real position reads
- real order creation
- automatic trading

It only preserves factor-research design notes for future review.
