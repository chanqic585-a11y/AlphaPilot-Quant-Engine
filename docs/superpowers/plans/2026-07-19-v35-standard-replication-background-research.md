# V35 Standard Replication And Background Research Implementation Plan

> Execute in the isolated Quant worktree. Keep existing Formal policies and historical evidence immutable.

## Task 1: Lock schemas with failing tests

Create tests for source records, canonical replications, family budgets, service state, and job state. Verify unknown fields that affect identity are hashed, missing provenance fails closed, and at most two variants exist per family.

## Task 2: Add source and replication registries

Add `research/source_registry/strategy_research_source_registry.json` and six files under `research/canonical_replications/`. Store only URL, license, concise summary, citation, mechanism, assumptions, adaptation limits, readiness, and identity hash inputs.

## Task 3: Implement registry loaders and contracts

Create `alphapilot/standard_replication/` with typed contracts, canonical hashing, registry validation, and family budget validation. Keep files small and family-neutral.

## Task 4: Implement CandidateAdapters

Add deterministic adapters for ready families and contract-only blocked adapters for families lacking PIT/event readiness. Reuse `formal_validation.candidate_adapter` and prove the Formal core does not import family modules.

## Task 5: Implement bounded background service

Create `alphapilot/research_service/` with queue, atomic checkpoints, single-writer lease, resource budget, health projection, and deterministic one-cycle service. It must support pause, resume, stale-lease recovery, and zero-winner completion.

## Task 6: Add command entry points

Add a Python CLI and PowerShell wrappers for one cycle, bounded continuous mode, pause, resume, and status. Continuous mode must have an explicit sleep, maximum cycles or operator stop, and no hidden infinite optimizer.

## Task 7: Integrate dual-track receipts

Append research-only state receipts to the V33 research ledger. Cross-track output may only be `immutable_release_ready`; no approval, Demo import, ARM, order, or Live side effect is allowed.

## Task 8: Documentation and verification

Update README and add V35 closeout. Run targeted tests, full Quant tests, compileall, config validation, safety scan, and staged whitespace checks. Commit locally, then publish only under the user's current explicit long-workflow authorization after all checks pass.
