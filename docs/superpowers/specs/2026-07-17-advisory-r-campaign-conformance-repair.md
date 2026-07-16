# Advisory-R Campaign Conformance Repair Specification

## Decision

V13.27.1.16 is an implementation correction, not a strategy search or parameter
optimization. The V15 zero-survivor result remains immutable historical evidence,
but it is classified as implementation-nonconformant and cannot support a market
mechanism conclusion.

## Frozen Boundary

The following V15 values are immutable:

- 10 candidate identities and 8 family identities.
- Feature, entry, initial-stop, exit-policy, maximum-hold, benchmark, universe,
  snapshot, cutoff, cost, gate, and routing definitions.
- Every V15 artifact byte and hash.
- Advisory-R target R: target values remain candidate metadata; 2R is not a hard
  admission gate and must not be reintroduced by the correction.
- Locked OOS reads, formal evidence, Release, Demo ARM, and orders remain zero.

## Repair Boundary

The corrected runner must:

1. Compile candidate-specific signals and structure masks from frozen fields.
2. Fail closed when a frozen field or rule is unsupported or unused.
3. Use `alphapilot.exit_policy.engine.replay_exit_policy` as the only authority for
   stop, target, partial, trailing, structure, time, and gap execution.
4. Model pair-relative candidates as synchronized two-leg events and S09 as a
   capital-competing long-short portfolio. If the existing engine cannot faithfully
   represent a frozen definition, mark the candidate `implementation_blocked`.
5. Implement each frozen simple benchmark under the same data, event timing, cost,
   and capital-competition convention. Benchmark increment remains diagnostic.
6. Preserve unavailable funding as null, never zero-filled evidence.

## Additional Audit Controls

These controls supplement the user-provided prompt:

- Capture a pre-repair manifest of every V15 artifact and compare it after the run.
- Separate code-correction deltas from parameter deltas. Event changes caused by
  faithful execution are expected; parameter, candidate, gate, universe, and cost
  changes must remain zero.
- Compute event parity against independently projected formal-engine output, not
  against the known-nonconformant V15 event rows. V15-versus-corrected differences
  are reported separately as correction attribution.
- Hash the conformance compiler, formal exit engine, structure compiler, and
  benchmark compiler into the new preregistration.
- Freeze and commit the corrected preregistration before reading corrected results.
- Run exactly one corrected prefilter attempt and append it to the trial ledger.
- If zero candidates survive, stop. If candidates survive, route only to a future
  version; do not run walk-forward, Locked OOS, Release, ARM, or orders here.

## Acceptance

The correction is accepted only when all tests pass, all 10 candidates have an
explicit conformance outcome, no silent fallback is reachable, V15 artifact hashes
are unchanged, and the corrected campaign produces a complete auditable report set.

