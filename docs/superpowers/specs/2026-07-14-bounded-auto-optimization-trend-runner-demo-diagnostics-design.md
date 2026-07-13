# Bounded Auto-Optimization, 2R Trend Runner, and Demo Diagnostics Design

## Goal

Advance AlphaPilot in three related areas without weakening its evidence or execution boundaries:

1. Automatically create and backtest bounded challenger versions after a strategy fails.
2. Add an explicit exit-mode challenger that closes 50% at +2R and manages the remainder with a deterministic trend runner.
3. Make OKX Demo explain exactly whether a strategy was evaluated, matched, sized, rejected, or submitted, and recover safely when the Console process changes.

The system may stop with a strategy still failed. It must never tune indefinitely or force a strategy through a gate.

## Current Evidence

- Existing failed 5m and 15m strategies are not marginal misses. Their formal reports show negative average net R, low profit factors, severe drawdown, and simultaneous failure of cost-stress and positive-expectancy gates. Blind parameter search is therefore likely to overfit.
- The repository already supports immutable parent/challenger lineage and queueing an imported optimized version. This design extends those patterns instead of replacing them.
- The Demo database contains 20 completed close-batch evaluations from July 11-13. The old batches evaluated five 1h Releases each hour and all ten Releases at daily boundaries, but recorded zero matched signals and zero orders.
- Those completed batches used the old Top20 screening scope. A later public-only Top100 audit found one or two signals for each of the five 1h short-rejection strategies. The five 1D long strategies remained unmatched, primarily because the BTC regime was bearish and the long-entry structures were absent.
- Current immutable contracts specify Top100, but no Top100 close batch has been committed after their migration. `AutoExecutionCheckpoints` and `DemoExecutionRecords` are both empty.
- The current Console PID is different from the persisted armed PID. Runtime state is `disarmed` with `process_arm_required`, so the current process is not evaluating Releases at all.

These facts mean that "ten strategies ran for two days without a trade" is not one condition. It is a combination of valid old Top20 zero-match batches, a Top100 audit that did find 1h signals, and a later runtime that never armed or evaluated the migrated Top100 Releases.

## Approaches Considered

### 1. Manual optimization only

Keep the existing Improve action and require an operator to create every challenger. This is easy to audit but too slow for repeated weak candidates and does not provide a repeatable research budget.

### 2. Tune until a historical pass is found

Continuously change parameters and re-run backtests until the gates pass. This can produce a green badge, but leaks information from validation data, overfits history, and makes the pass meaningless. This approach is rejected.

### 3. Bounded automatic challenger campaign

Diagnose the failed run, modify only allowlisted parameters, use development and walk-forward data for selection, and stop after a small fixed budget. Run locked validation once for the selected challenger and never use that result for another automatic retry. This is the selected approach.

## Architecture Decision

Implement three isolated units:

1. `OptimizationCampaign` in the Quant Engine owns bounded challenger generation and research evaluation.
2. `PartialTargetTrendRunner` in the backtest/execution model owns the new deterministic exit behavior.
3. `DemoEvaluationAudit` and launcher ARM handoff in the Control Console own runtime recovery and per-layer execution evidence.

The units communicate through immutable strategy definitions and persisted reports. The optimizer does not mutate a Demo Release, and Demo does not alter research parameters.

## Bounded Optimization Campaign

### Lifecycle

```text
failed strategy version
  -> diagnose
  -> eligible for bounded tuning OR structural/data stop
  -> create immutable challenger
  -> development + walk-forward evaluation
  -> retry within budget OR select best challenger
  -> one locked formal validation
  -> pass OR stop failed
```

Persist at least:

- campaign ID and root strategy version ID
- immutable parent and challenger version IDs
- attempt index and maximum attempts
- parameter diff and diagnosis that justified it
- development and walk-forward metrics
- formal validation status
- terminal stop reason

### Budget and Concurrency

- Default maximum: three automatic challenger attempts per failed root version.
- Only one automatic challenger for a root version may be active at a time.
- A manual new research hypothesis starts a new root/campaign; it does not reset an exhausted campaign silently.
- Data-integrity failure, missing evidence, or unsupported family stops immediately without guessing parameters.
- A structurally weak development result may stop early. The initial rule is: development profit factor below 0.80, development average net R at or below -0.15R, and at least three independent failed gates. The diagnosis must state `structural_redesign_required`.

### Parameter Boundary

- Each strategy family has an explicit parameter allowlist and numeric bounds.
- An attempt changes at most two allowlisted parameters.
- Direction, timeframe, market type, data splits, cost model, and universe definition are not tunable parameters.
- `targetR` remains at least 2.0 and cannot be reduced to manufacture a pass.
- The partial-target trend runner is a separate structural challenger, not an automatic parameter tweak.

### Data Separation

- Challenger selection may use development and walk-forward results only.
- Holdout and locked out-of-sample data are not part of the optimization objective.
- After the bounded search selects its best eligible challenger, locked formal validation runs once.
- If locked validation fails, the campaign ends as `formal_validation_failed`. The failure cannot trigger another automatic challenger in the same campaign.
- Zero-trade candidates fail sample sufficiency; the optimizer may not treat no activity as low risk or success.

### Objective

Reuse the existing profitability, drawdown, cost-stress, sample, and stability gates. Do not optimize win rate alone. Rank candidates only after positive net expectancy and cost-stress requirements are met on development and walk-forward data. A higher score never overrides a failed hard gate.

### Terminal Outcomes

- `passed`: all required gates passed.
- `budget_exhausted`: three attempts completed without an eligible challenger.
- `structural_redesign_required`: early structural weakness made further local tuning wasteful.
- `data_evidence_blocked`: data integrity or evidence was insufficient.
- `formal_validation_failed`: selected challenger failed one-shot locked validation.

All non-passed outcomes remain failed. None is promoted automatically.

## Option B: 2R Partial Target and Trend Runner

Create a new immutable exit-mode challenger with these frozen rules:

- Initial stop remains the strategy's existing -1R hard stop.
- At +2R, close 50% of the original position.
- After the partial fill, the remaining 50% uses a one-way stop updated only from confirmed closed candles.
- Long runner stop: the greater of `entry + 1R` and `highest confirmed close since entry - 2.5 * ATR14`.
- Short runner stop: the lower of `entry - 1R` and `lowest confirmed close since entry + 2.5 * ATR14`.
- The stop can tighten but never loosen.
- The existing maximum-hold rule remains a final exit.
- Fees, slippage, funding, partial-fill rounding, and minimum contract size are included in both backtest and Demo accounting.

`2R` remains the first gross reward target, not a guarantee that the complete trade realizes 2R. For example, half at +2R and half stopped at +1R realizes +1.5R gross before costs. UI and reports must show first-target R, gross realized R, and net realized R separately.

No AI or discretionary text decides the exit price. The rule is deterministic, reproducible, and symmetric for long and short positions.

## Demo Runtime and Zero-Match Diagnosis

### ARM Handoff

- Demo remains fail-closed when the persisted armed PID differs from the current Console PID.
- After the secure launcher receives process-only Demo credentials and the explicit automation confirmation phrase, it must wait for the new listener, verify health, and atomically arm the current PID.
- A stale armed PID must be replaced by that launcher handshake. The browser must not pretend Demo is running while `armedForCurrentProcess` is false.
- Credentials remain process-only and are never written to SQLite, JSON, logs, or reports.
- If the current process lacks credentials, the system stops and asks once for launcher re-entry. It must not loop or silently downgrade.

### Per-Close-Batch Audit

For each confirmed candle close and Release, persist bounded aggregate evidence:

- eligible Release count
- market universe size, liquidity-qualified count, and deep-screened count
- evaluated Release count
- entry-rule check counts and top failed checks
- matched signal count and near-miss count
- sizing rejection count and reasons
- risk rejection count and reasons
- latency/price-deviation rejection count and reasons
- order attempts, accepted orders, failed orders, and exchange business codes
- close timestamp, processing duration, current PID, and next evaluation time

Do not persist API credentials. Full raw factor payloads are unnecessary; bounded aggregate counts and a small number of public-data near misses are sufficient.

### UI State

Show mutually exclusive, explicit states:

- not armed
- armed, waiting for confirmed close
- evaluated with zero matches
- matched but rejected by sizing/risk/latency
- order submitted
- order failed

The card must show the last confirmed close, evaluated strategy count, Top100 screened count, matches, order results, next close time, and one actionable next step. It must never summarize zero evaluated Releases as zero matched Releases.

### Operational Recovery Order

1. Arm the current process through the secure launcher handshake.
2. Confirm `armedForCurrentProcess=true` and public market runtime warm.
3. Wait for one confirmed 1h close and verify that all five 1h Releases are evaluated against Top100.
4. If signals match but orders remain zero, inspect sizing, risk, latency, and exchange-code counts.
5. If repeated Top100 closes produce zero matches, collect failed-check distributions across several independent closes and create a new immutable research challenger. Do not loosen an active Release in place.
6. Keep the 1D long Releases inactive when the frozen BTC regime gate rejects the current bear regime; this is a valid no-trade outcome.

The existing public-only Top100 audit already found one or two candidates for each 1h short-rejection strategy, so runtime recovery and formal Top100 close-batch evidence come before any parameter relaxation.

## Safety Boundaries

- No Withdraw integration.
- No raw credential persistence or credential logging.
- No mutation of immutable Demo Releases.
- No automatic force-pass after optimization budget exhaustion.
- No use of holdout/locked OOS results to generate another automatic attempt.
- No automatic Live promotion from backtest or Demo results.
- Demo orders remain subject to existing account, risk, idempotency, market-data, and latency gates.
- Live automation remains outside this design.

## Verification

### Quant Engine

1. Test-first campaign tests cover attempt counting, immutable lineage, parameter allowlists, single-active-child enforcement, early structural stop, and terminal exhaustion.
2. Split-integrity tests prove locked validation does not feed challenger generation.
3. Backtest tests cover long and short partial exits, one-way ATR trailing, +1R floor, max hold, fees, slippage, funding, and contract rounding.
4. Regression tests prove fixed-2R strategies retain their existing behavior.

### Control Console

1. Launcher tests prove stale PID replacement only occurs after credentials and explicit automation confirmation are present.
2. Runtime tests prove current-PID ARM, confirmed-close evaluation, and fail-closed behavior without credentials.
3. Audit tests prove zero evaluated, zero matched, sizing reject, risk reject, and order failure remain distinct.
4. Top100 replay tests evaluate all ten immutable Releases using public data without creating orders.
5. Full tests, compileall, config validation, safety scan, and `git diff --check` must pass in both repositories.

## Rollout

1. Implement Demo ARM handoff and audit observability first; verify a Top100 1h close without changing strategy parameters.
2. Implement the bounded optimization campaign and run it only against failed research versions.
3. Implement the Option B exit challenger and formally compare it with the fixed-2R parent.
4. Create new immutable Demo Releases only for challengers that pass all formal gates.

This order fixes the current false "running but not evaluated" state before adding more strategy variants.
