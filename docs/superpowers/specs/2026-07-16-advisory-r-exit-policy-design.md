# AlphaPilot Advisory-R Exit Policy Design

**Date:** 2026-07-16
**Status:** approved by user
**Scope:** Quant research campaigns and OKX Demo strategy admission
**Policy version:** `advisory_r_exit_policy_v1`

## Decision

AlphaPilot will temporarily remove the rule that every new strategy must target at least 2R. R remains the common risk-accounting unit, but a fixed 2R target is no longer a strategy-creation or Demo-admission gate.

This change does not relax the initial stop, cost, expectancy, drawdown, sample, walk-forward, locked-OOS, or immutable-release controls. It changes exit-policy representation and admission semantics, not the requirement for falsifiable evidence.

## Verified Current State

The latest formal preregistration, `phase3c_campaign_dece86da86243317f47c517466acc1b9e901553fe80b802c8ce71d5c7e7cfc50`, still uses:

- `riskPolicy.minimumTargetR = 2.0`;
- candidate targets of `2.2R, 2.2R, 2R, 2R, 2R, 2R`;
- `CandidateSpec` validation that rejects `targetR < 2`;
- a backtest simulator that exits at a fixed `candidate.targetR` price.

The existing `build_event_exit_geometry` helper exposes a partial-exit shape, but it is not connected to the formal campaign simulator and still rejects a remaining target below 2R. Console Demo admission also treats a target below 2R as a blocker.

Therefore the recent campaign was not merely labelled with 2R: it was constructed and simulated under a fixed 2R-or-better exit constraint. Its failures must remain historical evidence and must not be rewritten after this policy change.

## Goals

1. Remove fixed 2R as a hard gate for new research candidates.
2. Support multiple bounded, preregistered exit policies.
3. Keep realized gross R and net R as comparable metrics.
4. Preserve the frozen initial stop and prohibit stop widening.
5. Keep cost-adjusted positive expectancy, PF, drawdown, sample sufficiency, purged walk-forward, locked OOS, stress tests, and concentration controls as gates.
6. Let valid non-2R candidates enter OKX Demo when all other research and safety evidence passes.
7. Preserve old campaigns and immutable releases byte-for-byte.

## Non-Goals

- No retroactive recomputation of historical campaign evidence.
- No mutation of existing immutable Demo or live releases.
- No forced winner and no automatic pass after bounded optimization fails.
- No stop widening, unlimited averaging down, martingale sizing, or missing-evidence substitution.
- No change to live-trading admission in this patch.
- No raw API key persistence and no Withdraw integration.

## Chosen Model

### Exit policy is preregistered and hashed

New candidates use an immutable `exitPolicy` object. Supported initial modes are:

1. `fixed_r`: a positive fixed target in R. The target may be below, equal to, or above 2R.
2. `partial_then_trailing`: close a preregistered fraction at a preregistered R threshold, then trail the remainder by a preregistered ATR distance.
3. `structure_or_time`: exit on a preregistered structure-invalidating condition or at the maximum holding period.
4. `hybrid`: combine one bounded partial exit with a trailing or structure/time exit for the remainder.

Every mode retains the original fixed stop. All parameters are included in the candidate definition hash. Runtime discretion cannot silently alter an exit policy.

### Backward compatibility

Existing candidates with `targetR` and no `exitPolicy` remain valid legacy `fixed_r` candidates. Their target and historical results do not change.

New campaign preregistrations use a new schema version and record:

```json
{
  "riskMetric": "R",
  "targetRGateMode": "advisory",
  "minimumTargetR": null,
  "initialStopMayWiden": false,
  "exitPolicyRequired": true
}
```

`targetR` remains reportable when a policy has a fixed target, but it is optional and is not a pass/fail gate.

## Simulation Semantics

- Entry remains next-bar-open unless a campaign preregisters another causal rule.
- Same-bar stop/exit ambiguity remains stop-first and conservative.
- Partial exits use weighted gross R and weighted costs.
- Trailing stops may only tighten risk; they can never widen beyond the current or initial stop.
- Structure exits may only use information available at that bar.
- Time exits use the preregistered maximum holding period.
- Every event reports entry, initial stop, exit-policy hash, exit legs, gross R, fees R, slippage R, spread R, funding R, and net R.

## Admission Gates

The following remain hard gates:

- minimum event and history coverage;
- development and OOS profit factor;
- positive cost-adjusted average net R and total net R;
- maximum drawdown;
- positive purged walk-forward folds;
- stress-cost profitability;
- concentration limits;
- locked holdout access discipline;
- complete immutable strategy definition and exit policy.

The following is removed as a hard gate:

- fixed target R greater than or equal to 2.

A lower target does not create a pass by itself. A candidate with weak or negative cost-adjusted evidence still fails and is retained as failed evidence.

## Console Demo Boundary

The active strategy-validation and Demo workflow will:

- accept the new policy version;
- display exit-policy mode instead of `target >= 2R` as required evidence;
- require a complete immutable exit policy;
- keep target R as an advisory field when present;
- reject missing or mutable exit definitions;
- preserve existing 2R releases under their original schema;
- leave live-release and live-risk-profile rules unchanged in this patch.

Retired local-simulation labels are not part of this patch unless they are still reachable from the active user flow.

## UI Wording

Active research and Demo screens will use:

- `退出方式：固定 R / 分批后追踪 / 结构或时间 / 混合`
- `目标 R：参考指标，不作为通过硬门槛`
- `实际净 R：成本后结果`

They must not claim that removing 2R makes a strategy profitable or ready for live trading.

## Migration and Versioning

- Historical schema v1 preregistrations remain read-only.
- New preregistrations use a new schema version and policy identifier.
- Importers support both schemas.
- Existing hashes and releases are never regenerated.
- New candidate hashes include the complete exit policy.

## Test Strategy

Tests must be written before implementation and cover:

1. A new candidate with a valid fixed target below 2R is accepted.
2. A candidate with a bounded trailing or structure/time exit and no fixed target is accepted.
3. A candidate without a complete exit policy is rejected.
4. Invalid or unbounded exit parameters are rejected.
5. The initial stop cannot widen in any mode.
6. Partial exits calculate weighted net R and costs correctly.
7. Legacy fixed-2R candidates produce unchanged events and hashes.
8. New preregistrations record advisory target-R policy.
9. Formal gates still reject negative expectancy, weak PF, excess drawdown, insufficient samples, failed stress tests, or holdout misuse.
10. Console Demo admission accepts a complete non-2R exit policy but rejects incomplete definitions.
11. Existing immutable Demo releases remain unchanged.
12. Live admission behavior remains unchanged.

## Rollout

1. Add failing Quant contract and simulator tests.
2. Implement the versioned exit-policy model and simulation engine.
3. Update reports and preregistration output.
4. Add failing Console import and Demo-admission tests.
5. Update active Console Demo evidence and wording.
6. Run targeted tests, full repository tests, compile checks, and diff checks.
7. Generate a new research campaign only after code and policy artifacts are frozen.

## Success Criteria

- New strategies are no longer rejected solely because their target is below 2R or because they use a bounded non-fixed exit.
- R accounting and all evidence-quality gates remain intact.
- No historical campaign, release, or report is modified.
- No strategy is forced through the funnel.
- Demo can admit a fully evidenced strategy using the new policy, while live admission remains unchanged.
