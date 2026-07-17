# V18 Reusable Formal Validation Core Implementation Plan

## Objective

Make the V18 formal-validation engine candidate-agnostic before its first
formal result, without changing any frozen S01 trading or validation policy.

## Tasks

1. Add failing tests proving the core has no S01 imports, candidate identity is
   explicit, artifacts use campaign/candidate paths, and a synthetic candidate
   can run through the core.
2. Add the generic `CandidateAdapter` protocol, adapter registry composition
   layer, and S01 adapter.
3. Refactor formal input and V18 reporting to accept an adapter rather than
   importing S01 functions.
4. Add independent `VersionedPolicyObject` wrappers for Capacity, Cluster,
   Beta, and Ranking definitions and verify their hashes and versions.
5. Add a generic formal-run command with `--preregistration` and
   `--candidate-id`; retain the S01 command as a compatibility wrapper.
6. Run targeted, formal-validation, full, compile, config, and safety checks.
7. Commit and push pre-result implementation, regenerate/freeze the
   preregistration against the pushed commit, commit and push it, then run the
   remote-freeze audit.
8. Execute the one formal research run only after the remote-freeze audit
   passes; report commit, push, counters, and artifacts.

## Stop Conditions

- Do not open formal inputs before remote freeze.
- Do not work around publication or credential failures.
- Do not change S01, capital-policy values, ExitPolicy, gates, universe, costs,
  or splits.
- Do not create Release, Demo ARM, orders, or live-trading capability.
