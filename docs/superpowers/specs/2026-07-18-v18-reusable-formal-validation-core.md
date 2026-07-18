# V18 Reusable Formal Validation Core Design

## Status

Approved by the user's conditional V18 instruction. This design is pre-result
work only. It must be completed, tested, committed, pushed, and remotely frozen
before any formal input or result is opened.

## Frozen Boundaries

The refactor must not change S01 strategy logic, capital-policy numeric values,
ExitPolicy, gates, universe, costs, or split definitions. It must not create a
Release, arm Demo, place an order, or access Locked OOS content.

## Architecture

### Generic core

The formal-validation core owns input verification, fold assignment, capital
replay, statistics, evidence publication, and the one-run ledger. Core modules
depend only on a `CandidateAdapter` protocol and versioned policy objects. They
must not import `advisory_r_campaign`, `s01_*` adapter modules, or S01 strategy
implementations.

### Candidate adapters

Each candidate family is integrated through one adapter with a stable adapter
ID, adapter version, candidate ID, candidate resolution, raw replay, and parity
execution. The S01 adapter remains behavior-identical and is selected by the
composition layer. A second synthetic adapter fixture must execute the same
core path in tests.

### Policy objects

Capacity, Cluster, Beta, and Ranking remain separate modules and are exposed as
independent immutable `VersionedPolicyObject` instances. Their existing frozen
definitions and numeric values remain unchanged; the wrapper records policy
kind, version, schema, and definition hash without introducing candidate
knowledge.

### Command and artifacts

The generic command accepts both a preregistration path and candidate ID. The
candidate ID must match the frozen preregistration. Formal artifacts are written
under:

```text
<output-root>/<campaignId>/<candidateId>/
```

No command or output path may hard-code S01. The existing S01 command remains a
compatibility wrapper over the generic command.

## Publication Sequence

1. Finish and test pre-result architecture.
2. Commit and push implementation.
3. Regenerate the V18 preregistration against the pushed implementation commit.
4. Commit and push the frozen preregistration.
5. Pass remote-freeze audit.
6. Only then claim the one formal run and publish formal artifacts.

Any publication or freeze failure leaves formalRunCount and resultReadCount at
zero.
