# V36 TSMOM Formal Handoff Plan

## Goal

Make the two Development-selected V35 TSMOM candidates executable through the
candidate-neutral Formal Validation Core without changing any Formal policy,
reading Locked OOS, or creating a Release.

## Frozen Candidates

- `v35_tsmom_source_replication`
  - selected trial: `v36_trial_ec2562d73795444e90789e7f77a3e129030b7d92c0f3614cf3f33375fdaf41c0`
  - parameter scale: `1.0`
- `v35_tsmom_crypto_adaptation`
  - selected trial: `v36_trial_43b2c0f5804b1f0596bc6d5691d79013699a5e1b3db0a07e7a3332ac3f6f0599`
  - parameter scale: `1.0`

## Boundaries

- Keep the Formal Validation Core candidate-neutral.
- Resolve candidates only through `CandidateAdapter`.
- Register only the two selected TSMOM identities; all other V35 candidates
  remain fail-closed.
- Preserve exact candidate, trial, strategy-definition, exit-policy, snapshot,
  code-commit, split, cost, capital, ranking, cluster, beta, capacity, and gate
  identities.
- Keep funding explicit. Missing or incomplete funding evidence blocks Formal
  readiness; it is never treated as zero.
- Do not read Formal input or Locked OOS until the implementation commit and
  preregistration are both pushed and the remote-freeze audit passes.
- Do not create a Release, approve, ARM, access a private account, or place an
  order in this handoff.

## Implementation

1. Extract a reusable deterministic TSMOM signal/replay engine from the V36
   Development runner.
2. Make `CanonicalReplicationCandidateAdapter` executable only for the two
   frozen TSMOM variants and expose structural `load_signals` evidence.
3. Add an independent translated signal path and require exact parity.
4. Register the two candidate IDs in the composition-layer adapter registry.
5. Add tests for registry resolution, deterministic signal identity, replay,
   parity, frozen hashes, selected-trial binding, and fail-closed identities.
6. Run targeted and full tests plus compile, configuration, safety, and diff
   checks.
7. Commit and push the implementation branch.
8. Generate funding-aware preregistrations from the pushed commit, commit and
   push them, then run remote-freeze and zero-budget preflight checks.
9. Run Formal once per candidate only if every preflight gate passes. Preserve
   a zero-survivor or blocked result without relaxation or rerun.

## Acceptance

- The generic Formal runner imports no V35 candidate implementation.
- Both selected TSMOM candidates resolve through the common adapter registry.
- Non-selected V35 candidates remain unregistered or fail-closed.
- Reference and translated structural signals have exact deterministic parity.
- Replay events contain canonical candidate, symbol, direction, signal, entry,
  exit, cost, and R evidence.
- Before Formal execution, `formalRunCount`, `resultReadCount`, and
  `lockedOosAccessCount` remain zero.
- No Release, Demo, Live, credential, private-account, or order capability is
  added.
