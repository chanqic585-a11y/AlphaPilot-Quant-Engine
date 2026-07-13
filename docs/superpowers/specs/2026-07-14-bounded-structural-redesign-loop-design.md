# AlphaPilot Bounded Structural Redesign Loop Design

**Date:** 2026-07-14  
**Status:** Approved design  
**Scope:** Research backtest workflow only

## 1. Goal

When a formal research backtest is classified as structurally weak, AlphaPilot
must archive the failed immutable version, extract a split-safe failure profile,
create exactly one structurally changed immutable candidate, and place that
candidate back into the existing serial backtest workflow.

The loop may create at most three structural generations for one research
lineage. It is a bounded research process, not a mechanism that tunes historical
data until a strategy passes.

## 2. Non-goals

- Do not modify a running strategy or immutable Demo or Live release.
- Do not generate or execute arbitrary Python code.
- Do not use holdout or locked-validation results to design another generation.
- Do not bypass backtest, Local Forward, OKX Demo, or Live approval gates.
- Do not relax the `targetR >= 2R` requirement.
- Do not redesign a strategy in response to missing data, network failures,
  worker failures, or other engineering blockers.
- Do not run unbounded generations or force a strategy to pass.

## 3. Considered approaches

### 3.1 Endless parameter search

Continue mutating parameters until a historical gate passes. This is rejected
because it leaks research budget into repeated selection and encourages
overfitting.

### 3.2 Bounded deterministic strategy grammar

Convert split-safe failure evidence into a deterministic failure profile, select
one allowlisted structural recipe, and create one immutable candidate. This is
the selected approach because it is reproducible, auditable, and compatible
with the current workflow.

### 3.3 AI-generated executable strategy code

Allow an AI model to write a new strategy implementation. This is rejected for
the automatic path because the result is not sufficiently constrained or
reproducible. AI may later explain evidence or propose a human-reviewed research
specification, but it receives no execution authority.

## 4. Workflow

```text
formal backtest completes
  -> bounded optimizer classifies development_structurally_weak
  -> build split-safe failure profile
  -> check lineage budget and novelty
  -> select one allowlisted structural recipe
  -> create one immutable child version
  -> queue the child backtest
  -> archive the failed parent only after child registration and queueing succeed
  -> append immutable redesign and archive audit events
  -> existing serial worker drains the child
  -> repeat until pass, non-structural stop, or generation 3
```

If child registration, queueing, or audit persistence fails, the parent remains
visible and unarchived. The operation must be idempotent and safe to retry.

## 5. Generation budget

- Structural generation numbers are `1`, `2`, and `3`.
- The budget is separate from the existing three-attempt bounded parameter
  optimization budget.
- Only one active structural child may exist for a lineage at a time.
- Generation 3 may run a full formal backtest, but a structural failure from that
  run ends the campaign with `structural_generation_budget_exhausted`.
- A stopped lineage can be reopened only by a new explicitly versioned research
  campaign based on newly registered market evidence. It must not restart merely
  because the same endpoint or worker runs again.

## 6. Split-safe failure profile

The redesign service may read only development and walk-forward evidence used by
the existing selection path. It must remove holdout and locked-validation
metrics before recipe selection.

The failure profile contains:

- failed development and walk-forward gate names;
- profit factor, average net R, drawdown, trade count, and cost-stress result;
- direction, timeframe, signal family, exit policy, and current filters;
- overtrading, weak expectancy, drawdown concentration, sparse-sample, and
  transaction-cost sensitivity flags;
- a stable hash of the sanitized evidence.

Sparse samples or unavailable split evidence are data-evidence blockers and do
not trigger structural generation.

## 7. Controlled strategy grammar

The generator composes only registered and tested building blocks. The initial
grammar supports:

- signal families: trend pullback confirmation, compression release, and failed
  reclaim rejection;
- directions: long and short;
- regime filters: EMA trend alignment, BTC shock guard, and volatility band;
- confirmation filters: closed-candle confirmation, RSI range, relative volume,
  and ATR percentage range;
- exits: fixed 2R and the approved `two_r_half_atr_runner_v1` policy;
- risk invariants: positive stop distance, `targetR >= 2R`, bounded maximum hold,
  and no leverage or capital allocation mutation.

Recipes are versioned data, not generated source code. A deterministic mapping
selects a recipe from the failure profile. Examples:

- overtrading plus negative expectancy selects a stricter regime-confirmed
  trigger rather than merely increasing one threshold;
- high drawdown plus cost sensitivity selects a lower-frequency confirmation
  structure and stronger volatility guard;
- weak trend-following expectancy may select an allowlisted rejection structure
  while preserving timeframe and explicit direction;
- a recipe already used in the lineage is skipped.

If no novel recipe remains, the campaign stops with `no_novel_structural_recipe`.

## 8. Immutable lineage and audit data

Each generated definition includes `structuralRedesignLineage`:

```json
{
  "schemaVersion": "structural_redesign_lineage_v1",
  "campaignId": "stable hash",
  "rootStrategyVersionId": "root id",
  "parentStrategyVersionId": "failed parent id",
  "generation": 1,
  "maxGenerations": 3,
  "grammarVersion": "structural_strategy_grammar_v1",
  "recipeId": "registered recipe id",
  "failureEvidenceHash": "sanitized evidence hash"
}
```

The existing append-only audit store records:

- `structural_redesign_candidate_created`;
- `structural_redesign_parent_archived`;
- `structural_redesign_stopped`;
- the stable decision key, generation, recipe, parent, child, and stop reason.

No database migration is required. Existing StrategyVersion definition JSON,
status, parent lineage, WorkflowRun, and AuditEvent storage are sufficient.

## 9. Atomicity and idempotency

The service uses a stable decision key derived from campaign, parent version,
generation, evidence hash, and grammar version.

Processing order is:

1. Re-read the parent terminal run and current lineage state.
2. Return the existing child if the decision key was already processed.
3. Create the immutable child and its initial backtest run.
4. Queue the child.
5. Persist the redesign audit.
6. Archive the parent with a system actor and explicit redesign reason.

The repository operation should use one SQLite transaction. If the current
repository boundary cannot provide that transaction, implementation must add a
focused transaction method rather than rely on partial compensating writes.

## 10. Worker integration

The existing `run-selected-backtests` serial worker remains the sole formal
backtest slot. Structural children are added to the same drainable queue. The
existing continuous data-prefetch slot may prepare the next candidate, but the
feature must not increase full formal-backtest concurrency.

Recovery for terminal historical runs is provided through an idempotent CLI
command. Recovery uses an online SQLite backup first and never redesigns data or
worker failures.

## 11. Console behavior

The Strategy page shows concise lifecycle information:

- `自动重设计 1/3`;
- failed parent name and archived state;
- selected recipe summary;
- generated child name and current queue or run state;
- terminal reason when the campaign stops.

Archived parents remain available under history but do not remain in the active
failed lane. The Console must use an explicit backend capability flag before
showing structural-loop controls or status.

## 12. Stop conditions

The loop stops without creating a candidate when:

- the third structural generation has failed;
- no novel allowlisted recipe remains;
- the failure is not `strategy_performance`;
- development or walk-forward evidence is missing;
- locked or holdout evidence would be required for a decision;
- an active structural child already exists;
- child registration or queueing fails;
- an invariant such as `targetR >= 2R` would be violated;
- the selected candidate content duplicates any prior lineage version.

Stopping never promotes a strategy and never deletes its evidence.

## 13. Testing

### Unit tests

- deterministic failure-profile classification;
- holdout and locked metric removal;
- deterministic recipe selection and duplicate skipping;
- generation counter and three-generation stop;
- target-R and strategy-grammar invariants.

### Integration tests

- child creation, queueing, audit, and parent archive occur atomically;
- failed child creation leaves the parent active;
- repeated processing is idempotent;
- only one active child exists;
- data and worker failures never create structural candidates;
- serial worker drains a generated child without another user action.

### Console tests

- capability handshake controls the UI;
- current generation, archived parent, child state, and stop reason render in
  Chinese;
- active pages contain only the current child, while archive history retains the
  failed parent.

### Verification

- focused Quant and Console tests;
- full test suites for both repositories;
- `python -m compileall alphapilot`;
- Node syntax check for Console JavaScript;
- `git diff --check`;
- online backup and integrity checks before applying recovery to the real
  registry.

## 14. Rollout

1. Implement and test the grammar and split-safe failure-profile builder.
2. Add the transactional redesign service and audit projection.
3. Integrate it after bounded optimization returns
   `structural_redesign_required`.
4. Add CLI recovery for existing terminal structural failures.
5. Add Console capability and lifecycle display.
6. Verify with a cloned registry.
7. Back up the real registry, recover eligible current failures, and allow the
   existing serial worker to drain generated candidates.

Current Demo and Live releases remain untouched throughout rollout.
