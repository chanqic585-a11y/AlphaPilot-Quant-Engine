# AlphaPilot Event-Window Candidate And Shadow Research Design

**Date:** 2026-07-14
**Status:** Approved for implementation
**Scope:** 5m and 15m research candidates only

## 1. Goal

Generate five 5m and five 15m candidates that explicitly learn from archived
failures, pre-screen them on development-only public OHLCV, and submit only the
best auditable candidates to the existing formal backtest workflow.

This design does not promise that a strategy will pass. It prevents AlphaPilot
from repeatedly registering obviously weak variants merely to fill a quota.

## 2. Evidence Used

Archived short-cycle candidates failed in two distinct ways:

- broad bar-by-bar rules overtraded and remained negative after fee/slippage;
- strict same-bar event rules produced too few live matches because independent
  setup and confirmation conditions had to occur on one candle.

The successor therefore changes structure, not just thresholds:

- setup events may occur within the previous two or three closed candles;
- the current closed candle remains the confirmation and signal timestamp;
- trend, BTC shock, ATR, volume, and cost-aware frequency guards remain explicit;
- near misses are counted as shadow observations but never become orders.

## 3. Candidate Pool

The controlled pool contains multiple parameter variants of five allowlisted
families:

1. trend pullback and reclaim long;
2. breakout, retest, and continuation long;
3. liquidity sweep and reclaim long;
4. failed breakout reversal short;
5. failed EMA reclaim short.

Each candidate has immutable parameters, a 2R target, a positive ATR stop,
bounded holding time, and an `eventWindowBars` value of two or three.

## 4. Development-Only Pre-Screen

Pre-screening is a research triage step, not promotion evidence. It may use only
an early development interval and a declared subset of public market symbols.
It must never read formal holdout symbols or locked-OOS results.

Candidates are rejected before registration when they have:

- no useful trade sample;
- excessive event frequency;
- non-positive cost-adjusted expectancy;
- unacceptable drawdown relative to total R;
- extreme single-symbol concentration.

Ranking favors cost-adjusted expectancy, profit factor, sample sufficiency,
drawdown efficiency, and cross-symbol coverage. Selection is capped at five per
timeframe and at two variants of one signal family per timeframe.

The complete pool, rejected candidates, selected candidates, metrics, data
window, and stable report hash are saved in a research artifact. A formal
backtest still makes the only promotion decision.

## 5. Near-Miss Shadow Observation

Every event-window family exposes named checks. A shadow observation records a
closed candle when all but one or two checks pass. It records:

- strategy version or pool candidate key;
- symbol, timeframe, and closed-candle timestamp;
- failed check names and pass count;
- event-window age and direction;
- no order, no fill, and no promotion evidence.

Shadow observations are diagnostic only. They may guide a later immutable
successor version, but they cannot relax a running Release or trigger trading.

## 6. Workflow

```text
archived failure evidence
  -> controlled event-window pool
  -> development-only pre-screen
  -> select five 5m and five 15m candidates
  -> register immutable research versions
  -> queue existing serial formal backtest worker
  -> existing bounded optimizer / structural redesign
  -> pass, bounded stop, or user pause
```

Only one formal backtest worker remains active. Pool pre-screening is vectorized
and may run separately because it is not a promotion gate.

## 7. Invariants

- `targetR >= 2R` remains mandatory.
- Fee and slippage stress remain mandatory.
- Formal holdout and locked-OOS data remain isolated.
- Existing Demo and Live releases are unchanged.
- No API key, private account data, order, Withdraw API, or live execution is
  added.
- A failed strategy may remain failed after the bounded attempt budget.
- Selection diversity is enforced; ten renamed copies of one rule are invalid.

## 8. Verification

- unit tests for event-window timing and stale-event rejection;
- unit tests for BTC, volume, trend, and ATR guards;
- unit tests for near-miss shadow classification;
- unit tests for pre-screen rejection, ranking, diversity, and exactly 5 + 5;
- CLI/bootstrap idempotency tests;
- formal test suite and safety checks;
- registry backup and integrity check before registering real candidates.
