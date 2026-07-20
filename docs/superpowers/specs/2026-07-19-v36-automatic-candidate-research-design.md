# V36 Automatic Candidate Research Design

## Purpose

V13.27.1.36 extends the bounded V35 replication registry into a deterministic research route. It preregisters finite parameter neighborhoods, selects only from Development evidence, projects evidence through type-specific contracts, and routes already-produced Formal outcomes without weakening any Formal policy.

## Boundaries

- V35 commit `8d0a70db6b3b3cedfd81cf303964c5e265fbc094` is the immutable baseline.
- Each eligible family receives 3-8 preregistered parameter trials. Data-blocked families remain data-blocked and consume no Formal run.
- Parameter selection reads Development evidence only. Locked OOS, holdout, Demo, private account, and exchange credentials are outside this module.
- The comparison-panel identity freezes candidate set, trial set, dates, data snapshot, costs, capital policy, benchmark, and seed before Formal routing.
- Type projections are separate contracts for `directional`, `pair`, `portfolio`, and `event` evidence. Missing required fields fail closed.
- Formal validation remains owned by existing Formal modules. V36 accepts immutable Formal outcome records and checks their identity and approved taxonomy; it does not reproduce statistical calculations.
- The full approved Formal outcome taxonomy is preserved, but only `formal_pass` satisfies the section 8.5 complete-pass requirements and may emit `immutable_release_ready`. Every release remains `approved=false`, `demoArm=false`, and `orders=0`.
- A valid run may finish with zero winners or only data-blocked families. No rescue tuning is permitted.

## Components

1. `contracts.py` defines frozen trial, comparison panel, outcome taxonomy, and fail-closed errors.
2. `preregistration.py` deterministically expands 3 combinations for every eligible V35 candidate and writes the frozen campaign identity.
3. `selection.py` validates type-specific Development metrics and chooses a stable neighborhood using majority direction, non-spike PF/Net R, and bounded drawdown dispersion.
4. `formal_routing.py` validates Formal records against the frozen panel and maps outcomes to release, failure, or blocked routes.
5. `executor.py` composes the steps, writes atomic artifacts and a hashed manifest, and implements the V35 `ResearchExecutor` protocol.
6. `run_v36_candidate_research.py` provides a deterministic one-shot command suitable for V35 background orchestration.

## Artifact Contract

Each campaign directory contains:

- `preregistration.json`
- `development_projection.json`
- `neighborhood_selection.json`
- `formal_route.json`
- `immutable_releases.json`
- `campaign_summary.json`
- `artifact_manifest.json`

The manifest contains relative paths and SHA-256 hashes. The summary always reports candidate, blocked-family, Formal-run, result-read, Locked-OOS-read, release, ARM, order, and private-API counts.

## Determinism And Safety

Canonical JSON ordering and stable hashes make identical inputs produce identical identities. The executor rejects unknown candidates, trial budget violations, Locked-OOS-labelled Development evidence, panel drift, unapproved outcomes, and any execution-side effect. No API client is imported.
