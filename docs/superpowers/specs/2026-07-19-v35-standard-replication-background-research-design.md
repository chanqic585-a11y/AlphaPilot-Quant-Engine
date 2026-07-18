# V35 Standard Replication And Background Research Design

## Status

Approved for implementation on 2026-07-19 as part of the V33-V40 dual-track workflow.

## Product decision

AlphaPilot runs two isolated tracks in parallel:

- Research track: public data, source registry, canonical replication, bounded candidate generation, prefilter, Formal validation, and immutable release preparation.
- Execution track: OKX Demo engineering, isolated Live readiness, order lifecycle, reconciliation, risk controls, and operator UI.

The only bridge from Research to Execution is a content-addressed immutable Release plus an exact approval. Research never imports execution credentials and Execution never edits candidate, policy, gate, or Formal evidence.

## Why this design

Three approaches were considered:

1. Unbounded AI strategy daemon. Fast to generate variants, but impossible to audit and highly prone to result-driven overfitting. Rejected.
2. Manual-only research. Easy to control, but wastes time on deterministic refresh, validation, and routing. Rejected as the default.
3. Bounded deterministic research service over frozen templates. This keeps automation useful while retaining preregistration, finite budgets, immutable identity, and fail-closed gates. Selected.

## V35 scope

V35 changes candidate creation from free indicator composition to replication-first research. It adds:

- a source registry containing URL, license, short summary, citation, mechanism, and source quality;
- six canonical replication records;
- candidate adapters that satisfy the existing candidate-neutral Formal Validation protocol;
- a deterministic queue with leases, checkpoints, pause/resume, budgets, and health status;
- one-cycle and bounded-loop command entry points;
- read-only status artifacts for the Console.

V35 does not run Locked OOS, change gates, approve Releases, ARM Demo, submit orders, or enable Live.

## Canonical families

The registry contains these families:

1. Time-series momentum / Turtle, 4H and 1D, priority 1.
2. BTC-ETH relative value, priority 2.
3. Conditional residual mean reversion, priority 3.
4. Cross-sectional multi-factor, blocked until PIT universe readiness.
5. Event-driven, blocked until event provenance readiness.
6. Chan structure parser, parser/ranking/exit context only; not treated as a proven trading signal.

Each family has at most one source replication and one preregistered crypto adaptation. A third rescue version is prohibited.

## Background service contract

The service is deterministic and restart-safe:

```text
refresh data readiness
-> validate source registry
-> validate replication records
-> freeze campaign plan
-> instantiate bounded candidates
-> route to existing prefilter/Formal entry points
-> archive or stop at immutable_release_ready
```

Frozen defaults:

- maximumConcurrentCampaigns: 1
- maximumFormalRuns: 1
- maximumCampaigns: 3
- maximumFamiliesPerCampaign: 6
- maximumCandidatesPerCampaign: 12
- maximumFormalCandidatesPerCampaign: 4
- maximumStructuralRevisionPerFamily: 1
- maximumFormalBacktestsTotal: inherited 96

The scheduler owns no trading credentials. Its lease and state are atomic files under a program-specific report directory. A crash may leave an expired lease, but may not create a second active writer.

## State model

Service states:

```text
idle
running
paused
blocked
completed
```

Job states:

```text
queued
data_blocked
ready
running
prefilter_failed
formal_failed
immutable_release_ready
archived
```

The service records every transition with previous state, next state, reason code, artifact references, and hashes. Zero winners is a valid completion.

## CandidateAdapter boundary

Every executable replication implements the existing `CandidateAdapter` protocol. The Formal core imports only the protocol, never a family-specific module. Candidate ID must match preregistration, CLI request, and adapter identity exactly.

V35 adapters may expose deterministic signal replay for development fixtures, but cannot read Locked OOS or mutate frozen parameters.

## Data and copyright boundary

Source records store URL, license, summary, and citation only. No long source text is copied. A source with unknown or incompatible license can inform a mechanism note but cannot contribute copied code.

## Verification

- schema and source-registry validation;
- duplicate identity and missing-license rejection;
- candidate adapter contract tests;
- lease contention, checkpoint resume, pause/resume, and budget exhaustion tests;
- zero-winner and data-blocked routing tests;
- proof that no trade, credential, Demo, Live, approval, or Locked OOS API is imported;
- full `pytest tests -q --import-mode=importlib` regression.

## Documentation impact

The Quant README and AlphaPilot Docs repository will document the new paths, state model, source metadata boundary, and operator commands.
