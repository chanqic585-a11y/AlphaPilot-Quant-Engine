# AlphaPilot V18.1 Final Self-Check

## Identity and immutability

- V18 campaign: `advisory_r_v18_s01_capital_policy_correction_7ec0b57a7093dc7a`
- V18 freeze tag: `v13.27.1.18` at `aa2df4b5e8fc4e9c447edd3c5fef0a03de26ec01`
- V18 failure/closeout commit: `369119cee4704d5b9bbb7c14b674ae03e4a0a359`
- V18 predecessor artifacts changed: `0`
- V18.1 campaign: `advisory_r_v18_1_s01_formal_parity_runtime_correction_72ec6d1a8bf0fb71`
- Implementation commit: `32700c3dc36f33a1d79933f079ae19d3f2cf9b16` (pushed)
- Preregistration commit: `e72e1a386d18df7d7718a58fa63e3050fc292152` (pushed)
- Freeze commit/tag: `b60d0e191431a353e79f9c954c31d4de0be25c92` / `v13.27.1.18.1` (pushed)
- Authorization commit: `5a5b256a95161baa72e2026d8e05886ccd074a7c` (pushed)
- Result and mechanical closeout commit: `8ea936ad55e5f821c2d507a2e6d390c1200fad40` (pushed)

## Candidate-neutral contract

- CandidateAdapter contract version: `2`
- Signal identity contract hash: `formal_signal_identity_contract_v2_a478af3b4064b31d271e4028c0c9a6a24f7ac0d91241a931d3645183fc6515de`
- Formal Core S01 import count: `0`
- Real S01 signal fixture: passed
- Second synthetic candidate fixture: passed
- Signal ID golden fixture parity: passed
- Undefined-name check: passed

## Frozen contract diff

- Strategy / ExitPolicy / capital policy / Gate / universe / split / cost changes: all `0`
- Benchmark and statistical policy changes: `0`
- Only campaign identity, implementation commit, CandidateAdapter contract, and signal invocation repair changed as preregistered.

## Run accounting and Future OOS

- V18 operational attempt count: `1`; V18 result-read statistical increment: `0`
- V18.1 claim / attempt / result / read counts: `1 / 1 / 1 / 1`
- Formal result artifact count: `1` manifest containing `32` hashed files
- Future OOS ID: `s01_v18_1_future_locked_oos_1dedd104ae1e56a07af4841fa5f2f3ed9309b1fd73390a2daa54eb4bbb7b70a9`
- Future OOS start: `2026-07-17T20:00:00Z`
- Future OOS access / content / strategy-metric reads: `0 / 0 / 0`

## Formal result

- Five folds were emitted, but all accepted trade counts are `0` after capital rejection.
- Base / 1.5x / 2x: no accepted trades; PF is `undefined_no_losses`; average and total Net R are `0`.
- Funding Stress: not evaluable because registered same-exchange history is unavailable.
- Same-event benchmark: no accepted events; incremental Net R is `0`.
- Newey-West: sample `1939`, alpha `0`, one-sided p `0.5`.
- BH / DSR / PBO / White RC / SPA: `unavailable_predeclared`; BY was not produced and was not fabricated.
- Final route: `implementation_invalid_requires_new_campaign`.
- Primary blocker: `translation_parity_failed`; signal identity and exit-leg parity are `0%`.
- Capital acceptance and position-size parity are both `100%`.
- Formal Pass: false; Formal Evidence: `0`; Release: `0`; Demo ARM: false; Orders: `0`.

## Required next campaign

Create a newly preregistered campaign. Before any result run, load the frozen Freqtrade runtime, complete canonical event identity and fold assignment, freeze ranking evidence and point-in-time portfolio context, correct capacity data semantics, and register same-exchange funding stress input. Do not tune strategy parameters from this result.

## Validation

Pre-result focused tests: `17 passed`; formal validation: `132 passed`; statistical: `5 passed`; exit: `22 passed`; full suite: `891 passed, 157 subtests`. Final post-result verification is recorded separately in the closeout manifest.
