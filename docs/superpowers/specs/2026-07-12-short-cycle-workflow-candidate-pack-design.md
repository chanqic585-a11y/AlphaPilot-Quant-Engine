# AlphaPilot V13.27.3 Short-Cycle Workflow Candidate Pack Design

## Objective

Add ten executable short-cycle research candidates to the Strategy page so AlphaPilot can verify the complete lifecycle from immutable strategy registration through formal backtest, local forward, OKX Demo, and live-candidate review.

This version proves the workflow. It does not claim that any candidate is profitable, does not bypass a gate, and does not enable live trading.

## Product Decision

The immediate priority is system correctness:

1. New strategies appear only in the Strategy page as `backtest / awaiting`.
2. A one-click run executes the existing dual-layer data and formal backtest workflow.
3. Only a formal pass may create the next local-forward stage.
4. Only a completed local-forward pass may enter Demo preparation.
5. Only immutable Demo and live releases may move farther.
6. A parameter or rule change always creates a new immutable strategy version and restarts at backtest.

The later live canary may use a versioned risk profile with an approximately 500 USDT account cap. That live profile, credentials, order permission, and runtime ARM are outside this version and remain locked.

## Approaches Considered

### A. Frontend-only cards

Hard-code ten cards in the Strategy page.

- Advantage: fastest visual result.
- Defect: no executable rules, no data contract, no backtest, and no proof of the lifecycle.
- Decision: rejected.

### B. Executable candidate pack with one shared signal engine

Define ten immutable configurations, dispatch them through one allowlisted `short_cycle_v1` signal engine, register them idempotently, and let the existing workflow projection render them.

- Advantage: one signal meaning from backtest through later runtime stages; minimal duplication; auditable and testable.
- Cost: requires a formal-backtest dispatch path and candidate bootstrap command.
- Decision: selected.

### C. Repackage previous parameter-search results

Import old report rows as new strategy versions.

- Advantage: low implementation cost.
- Defect: the 15m V13.7.40 search explicitly rejected all candidates, while the selected 1h rows are too correlated and do not meet the requested 5m/15m scope.
- Decision: rejected.

## Candidate Pack

All candidates are hypotheses. All use OKX USDT perpetual markets, a point-in-time dynamic liquid universe, fixed `targetR = 2.0`, closed-candle signals, next-bar execution, fee/slippage/funding stress, purged walk-forward, unseen-symbol holdout, and locked OOS validation.

| # | Display name | Timeframe | Direction | Signal family | Initial parameters |
| --- | --- | --- | --- | --- | --- |
| 1 | 5m 放量突破延续 ATR1.2 | 5m | long | breakout_volume_long | lookback 48, breakout buffer 0.1%, volume ratio 1.8, RSI max 78, max hold 24 |
| 2 | 5m EMA20 回收反弹 ATR1.2 | 5m | long | ema_reclaim_long | trend tolerance 0.995, reclaim buffer 0.2%, RSI 42-68, volume ratio 1.0, max hold 24 |
| 3 | 5m 极端超卖收回 ATR1.2 | 5m | long | mean_reversion_reclaim_long | RSI low 28, volume ratio 1.0, max range 3%, max hold 18 |
| 4 | 5m 跌破放量延续 ATR1.2 | 5m | short | short_breakdown_momentum | lookback 32, breakdown buffer 0.1%, RSI max 48, volume ratio 1.2, max hold 24 |
| 5 | 5m 上影拒绝回落 ATR1.2 | 5m | short | short_rejection | upper buffer 0.3%, trend tolerance 1.005, RSI high 60, volume ratio 1.1, max hold 24 |
| 6 | 15m 趋势动量延续 ATR1.4 | 15m | long | momentum_continuation_long | trend tolerance 1.0, MACD tolerance 0.8, RSI 48-72, volume ratio 1.0, max hold 16 |
| 7 | 15m EMA20 回收反弹 ATR1.4 | 15m | long | ema_reclaim_long | trend tolerance 0.995, reclaim buffer 0.3%, RSI 42-72, volume ratio 1.0, max hold 16 |
| 8 | 15m 低波压缩突破 ATR1.4 | 15m | long | squeeze_breakout_long | lookback 32, squeeze window 96, squeeze ratio 0.8, volume ratio 1.2, max hold 16 |
| 9 | 15m 跌破放量延续 ATR1.4 | 15m | short | short_breakdown_momentum | lookback 32, breakdown buffer 0.1%, RSI max 50, volume ratio 1.1, max hold 16 |
| 10 | 15m 上影拒绝回落 ATR1.4 | 15m | short | short_rejection | upper buffer 0.3%, trend tolerance 1.005, RSI high 60, volume ratio 1.1, max hold 16 |

The pack intentionally contains six long and four short candidates across breakout, trend, mean-reversion, and rejection families. It does not repeat ten parameter variants of one family.

## Immutable Definition

Each version stores:

- `schemaVersion = short_cycle_strategy_definition_v1`
- `signalEngine = short_cycle_v1`
- `market = crypto_usdt_swap`
- `universePolicy = point_in_time_dynamic_liquid_usdt_swap`
- `timeframe = 5m | 15m`
- `direction = long | short`
- `targetR = 2.0`
- `researchOnly = true`
- family-specific entry parameters
- `stopAtr`, `maxHoldBars`, and conservative research risk metadata
- cost model with fee `0.0005` and slippage `0.0005`

Registration uses stable hashes. Re-running the bootstrap returns the same ten versions and must not create duplicates.

## Signal Semantics

The existing indicator implementation supplies EMA20/50/200, RSI14, MACD histogram, ATR14, volume ratio, Bollinger bands, candle body, and range. BTC three-bar return remains a market-shock filter.

The formal backtest dispatcher chooses the signal implementation from `definition.signalEngine`:

- Existing Alpha191 versions continue using their existing observer builder.
- New versions use `short_cycle_v1` and the declared family/parameters.
- Unknown engines or families fail closed.

Signals are evaluated only on completed candles. Historical candles build the rolling indicator window; only a current completed signal can create a simulated entry. A 15m strategy uses 15m signals and 5m execution paths. A 5m strategy uses 5m signals and 5m execution paths.

## Workflow and UI

The Quant registry remains the source of truth. The Control Console must not hard-code candidate cards.

1. `bootstrap-short-cycle` registers the ten families and versions.
2. Every version receives one initial `backtest / awaiting` WorkflowRun with the default backtest gate.
3. The Strategy page obtains the ten cards through the existing workflow projection.
4. Cards show Chinese display name, timeframe, direction, `2R`, current stage/status, and the one-click backtest action.
5. Failed or blocked runs remain visible with evidence-based diagnosis and retry/optimize/archive actions.
6. A formal pass creates local forward through the existing bridge; it does not jump to Demo.

## Backtest Evidence

The existing dual-layer contract remains mandatory:

- Local third-party data may be used only for research smoke.
- Official OKX public data is collected and frozen separately.
- The formal snapshot is point-in-time validated and content hashed.
- Required periods are 5m for 5m strategies and 15m plus 5m for 15m strategies.
- Dynamic historical universe, funding, instrument metadata, costs, latency, and slippage stress remain part of the contract.
- Purged walk-forward, unseen-symbol holdout, and locked OOS evidence are required.
- Formal minimum target is `2R`; existing profitability, sample-size, stability, and drawdown gates remain unchanged.

No candidate is labelled passed until the stored evidence passes the existing gates.

## Failure Handling

- Unsupported engine/family: block with an explicit strategy-definition diagnosis.
- Missing local data: continue to official preparation instead of inventing data.
- Missing or invalid official partitions: preserve checkpoint and block or resume safely.
- No trades: fail the sample-size gate; do not optimize automatically.
- Poor performance: retain the immutable failed version and offer a new challenger version.
- Process interruption: reuse the current WorkflowRun and checkpoint; do not create a duplicate run.

## Safety Boundary

- No API key changes.
- No Trade or Withdraw API additions.
- No Demo release creation during registration or backtest.
- No live release, live order, or automatic promotion.
- No claimed win rate or profitability before formal evidence exists.
- Existing Demo runtime and process-only credentials are not restarted or modified by this work.

## Test Design

Tests are written first and must prove:

1. The catalog contains exactly ten unique entries: five 5m and five 15m.
2. Every entry has `targetR = 2.0`, a supported family, complete required parameters, and a valid direction.
3. Bootstrap is idempotent and creates ten StrategyVersions, ten initial awaiting backtest runs, and zero Demo/Live releases or orders.
4. Workflow projection exposes all ten entries in the Strategy page source data.
5. The formal dispatcher uses the short-cycle engine and converts completed signals into the existing fixed-R evaluation path.
6. Unknown engines/families fail closed.
7. Existing Alpha191 formal-backtest behavior remains unchanged.
8. The Control Console renders the ten strategy cards without static duplication if any display adjustment is required.
9. Full Quant and Console regression, compile, diff, and safety checks pass.

## Acceptance Criteria

1. Ten executable immutable candidates exist, split 5/5 across 5m and 15m.
2. They appear in the Strategy page only under `待回测` after registration.
3. Repeated registration creates no duplicates.
4. One-click backtest can derive a data contract and start the real dual-layer worker for each entry.
5. Formal backtest uses the same short-cycle family semantics that later stages can reuse.
6. No candidate is promoted by registration.
7. Existing workflow, Alpha191 run, Demo releases, runtime credentials, and live locks remain intact.
8. No strategy is described as profitable or usable before it earns formal evidence.
