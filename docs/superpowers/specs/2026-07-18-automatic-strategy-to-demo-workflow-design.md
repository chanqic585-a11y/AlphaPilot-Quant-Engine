# V19-V24 Automatic Strategy-to-Demo Workflow Design

## Status

Approved by the user through the V13.27.1.19-V13.27.1.24 long-workflow
prompt and the explicit instruction to analyze, summarize, and execute it.

## Objective

Build one resumable, append-only program that moves evidence through six
bounded stages:

```text
data capability -> hypothesis generation -> prefilter freeze ->
one-shot formal validation -> immutable release -> OKX Demo admission
```

The program coordinates existing AlphaPilot research, formal-validation,
release, and Console boundaries. It does not replace those engines.

## Frozen Baseline

The authority baseline is V18.3 at commit `f9f36f4`, with the V18.3 formal
campaign archived as `archive_s01_current_version`. V19-V24 must not rewrite
that result or reinterpret it as a pass.

The following existing contracts remain authoritative:

- candidate-neutral `CandidateAdapter` formal core;
- preregistration and remote-freeze checks;
- immutable strategy-validation release hashes;
- Console import as unapproved;
- exact release-hash human approval;
- independent Runtime ARM;
- engineering-smoke isolation from strategy evidence.

## Program Model

### Program state

The orchestration modules live under `alphapilot/research_factory/`, as the
single research-factory boundary requested by the workflow. One `ProgramState`
records the program ID, active campaign, stage, stage
attempt, budgets, immutable input hashes, last checkpoint, terminal route, and
human-gate status. State is stored as canonical JSON and updated atomically.

### Append-only ledger

Every material transition writes a ledger record with a monotonic sequence,
timestamp, event type, stage, campaign ID, candidate ID when applicable,
input/output hashes, and previous-record hash. Re-running a completed command
must be idempotent and must not consume a second formal run.

### Stage checkpoints

Each stage owns a checkpoint under:

```text
reports/automatic_strategy_demo/<programId>/checkpoints/<stage>.json
```

Checkpoint completion requires both a valid payload hash and the required
artifact manifest entries. A partial checkpoint resumes from its first
incomplete operation.

### Budgets

The immutable program budget is:

- maximum campaigns: 3;
- families per campaign: 8;
- variants per family: 2;
- candidates per campaign: 16;
- structural revisions per family: 1;
- formal candidates per campaign: 6;
- full backtests per campaign: 48;
- full backtests across the program: 144;
- Demo releases per campaign: 3.

Budget exhaustion routes mechanically; it never relaxes a gate.

## Stage Architecture

### V19: data capability

V19 inventories available fields with point-in-time semantics and assigns a
versioned data profile. Every field records source, availability timestamp,
verification status, causal-use permission, and fallback behavior.

Supported profiles are:

- `ohlcv_core_directional_v1`;
- `ohlcv_verified_turnover_v1`;
- `future_derivatives_v1` (declared unavailable unless verified data exists).

Candidate data gates fail closed. Missing derivatives fields may not be
reconstructed from future information or silently replaced by OHLCV proxies.

### V20: independent hypotheses and candidates

The first campaign supports only `directional_event`. It creates independent,
falsifiable mechanism families from the data profile, then at most two bounded
variants per family. The first-batch timeframe priority is `4h`, then `1h`;
`15m` is conditional on verified coverage and `5m` is disabled.

Each `HypothesisSpec` and `CandidateSpec` is canonical, hash-addressed, and
free of performance results. Semantic fingerprints deduplicate equivalent
ideas before any event replay. Candidates bind to the reusable formal core
through `CandidateAdapter`; the core must not import family-specific modules.

### V21: prefilter and freeze

V21 runs a bounded event prefilter, limits survivors, freezes the comparison
panel, and creates the formal preregistration before formal results exist.
Prefilter output is diagnostic only and cannot claim a formal pass.

Advisory-R exits are allowed. A fixed 2R target is not a universal candidate
gate. Economic gates remain preregistered and include costs, sample quality,
profit factor, average net R, drawdown, fold robustness, benchmark comparison,
concentration, parity, and OOS integrity.

### V22: one-shot formal validation

Formal execution accepts an explicit preregistration path and candidate ID.
It first proves the implementation commit is pushed and frozen, then claims
exactly one formal run per candidate. Result reads are counted separately.

Mechanical result classes are:

- `formal_pass`;
- `research_pass_no_clean_holdout`;
- `research_pass_funding_unavailable`;
- failed.

No result-driven mutation of exits, gates, universe, costs, split, or capital
policy is permitted. Campaign failure may start the next bounded campaign with
a new preregistration; it may not edit the failed campaign.

### V23: immutable release

Eligible evidence produces at most three hash-addressed releases per campaign.
Standard formal evidence creates `strategy_validation` releases. Strong
research evidence lacking only clean holdout or verified funding may create an
explicit `research_forward` release with its limitations preserved.

All releases arrive with:

```text
approvalRequired=true
approved=false
immutable=true
environment=demo
```

### V24: Console admission

Console imports releases without creating approval records, ARM state, orders,
or strategy statistics. It verifies release bytes and hashes, reports the
exact hash requiring human approval, and stops at
`blocked_waiting_exact_release_approval` until the user explicitly approves
that hash.

After approval, Runtime ARM remains a separate action. OKX Demo universe
checks and the first closed-candle scan may then run. Engineering smoke orders
remain permanently isolated from strategy evidence.

## Terminal Routes

Valid terminal states include:

- `completed_demo_admission`;
- `completed_research_forward_demo_admission`;
- `completed_zero_qualified_candidates`;
- `blocked_waiting_exact_release_approval`;
- a documented data, publication, credential, or runtime blocker.

Zero qualified candidates is a truthful successful closeout of the research
program, not an excuse to manufacture a release.

## Safety Boundaries

- No raw API credentials are stored or emitted.
- No Withdraw capability is introduced.
- No Live release, Live ARM, or Live order is created.
- No approval is inferred from an import, test, user identity, or prior hash.
- No preregistration, release, formal result, or ledger record is overwritten.
- No missing data is fabricated.
- No failed gate is relaxed after results are observed.
- Exact release-hash approval remains human-only.

## Verification Strategy

Every stage is developed test-first. Unit tests cover schemas, deterministic
hashes, budget limits, idempotent resume, causal data gates, semantic dedup,
formal one-run protection, release classification, import behavior, approval
separation, and zero-release routing. Integration tests cover interruption and
resume across all six stages without requiring private credentials or orders.
