# Advisory-R Campaign Conformance Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faithfully replay the frozen V15 Advisory-R candidates with one formal exit engine, freeze a new correction campaign, and run one bounded corrected prefilter without changing strategy parameters.

**Architecture:** Candidate compilers translate frozen definitions into causal signal, structure, pair, portfolio, and benchmark inputs. A conformance layer records every consumed frozen key and fails closed on unsupported or unused fields. The reporting layer freezes code hashes before results and writes corrected evidence without mutating V15.

**Tech Stack:** Python 3.12, pandas, NumPy, PyArrow, pytest, canonical JSON/SHA-256, PowerShell safety checks.

## Global Constraints

- V15 commit is `9262a00e808812477671cca850dcafaffc38cc55` and tag is `v13.27.1.15`.
- Candidate, parameter, gate, universe, snapshot, cutoff, cost, and routing changes are zero.
- 2R remains advisory; it is not a hard prefilter gate.
- V15 artifacts are read-only and must retain byte-identical hashes.
- Missing funding remains null/unavailable.
- Locked OOS reads, formal evidence, Release, Demo ARM, and orders remain zero.
- No Trade API, Withdraw API, credential storage, account reads, or execution is added.

---

### Task 1: Freeze V15 History and Conformance Contract

**Files:**
- Create: `alphapilot/advisory_r_campaign/conformance.py`
- Create: `tests/advisory_r_campaign/test_conformance.py`
- Create: `reports/advisory_r_campaign/advisory_r_v15_502e810045e366353db4dbcfa7d08fdf3/implementation_conformance_review.json`

**Interfaces:**
- Produces: `build_conformance_record(candidate, consumed, unsupported)` and V15 artifact manifest verification.

- [ ] Write failing tests for unused fields, hard-coded mismatches, unsupported fallback, and stable conformance hashes.
- [ ] Run `python -m pytest tests/advisory_r_campaign/test_conformance.py -q` and confirm RED.
- [ ] Implement canonical key-path projection and fail-closed validation.
- [ ] Record V15 as implementation-nonconformant without changing existing artifacts.
- [ ] Run the conformance tests and confirm GREEN.
- [ ] Commit `Record V15 implementation conformance failure without mutating history`.

### Task 2: Make the Formal Exit Engine the Sole Authority

**Files:**
- Modify: `alphapilot/exit_policy/engine.py`
- Modify: `alphapilot/exit_policy/exit_legs.py`
- Modify: `alphapilot/advisory_r_campaign/signals.py`
- Modify: `tests/exit_policy/test_engine.py`
- Modify: `tests/advisory_r_campaign/test_signals.py`

**Interfaces:**
- Consumes: frozen `ExitPolicy`, causal signal position, risk distance, ATR, structure mask, and optional funding.
- Produces: complete leg-level event records from `replay_exit_policy`.

- [ ] Add failing tests for trailing stop price R, weighted partial R, stop-first ambiguity, and stop/target/partial/trailing gaps.
- [ ] Add a failing campaign test proving the legacy hand-written simulator is unreachable.
- [ ] Implement conservative gap fills and nullable funding evidence.
- [ ] Replace `_simulate_event` with an adapter around `replay_exit_policy`.
- [ ] Run exit-policy and campaign signal tests.
- [ ] Commit `Unify Advisory-R campaign replay with the formal exit-policy engine`.

### Task 3: Compile Frozen Structure and Candidate Semantics

**Files:**
- Create: `alphapilot/advisory_r_campaign/structure_rules.py`
- Create: `alphapilot/advisory_r_campaign/pair_replay.py`
- Create: `alphapilot/advisory_r_campaign/portfolio_replay.py`
- Create: `tests/advisory_r_campaign/test_structure_rules.py`
- Create: `tests/advisory_r_campaign/test_pair_replay.py`
- Create: `tests/advisory_r_campaign/test_portfolio_replay.py`
- Modify: `alphapilot/advisory_r_campaign/signals.py`

**Interfaces:**
- Produces: causal structure masks, synchronized two-leg events, and capital-competing portfolio events.

- [ ] Add synthetic RED tests for all five frozen structure rules and next-bar-open execution.
- [ ] Add RED tests proving S01 recovery bars; S02 beta/lag; S03 confirmation; S05 baseline/turn; S08 prior bars; S09 quantiles/rebalance; and S10 correlation audit.
- [ ] Implement only the frozen rule kinds and fail closed for every other kind.
- [ ] Implement S04/S05/S06 two-leg accounting or mark an explicit implementation block.
- [ ] Implement S09 cross-sectional portfolio accounting or mark an explicit implementation block.
- [ ] Run all candidate-specific tests.
- [ ] Commit `Implement candidate-specific structure pair and portfolio semantics`.

### Task 4: Compile Benchmarks, Novelty, Event Identity, and Parity

**Files:**
- Create: `alphapilot/advisory_r_campaign/benchmarks.py`
- Create: `alphapilot/advisory_r_campaign/novelty.py`
- Create: `alphapilot/advisory_r_campaign/event_identity.py`
- Create: `tests/advisory_r_campaign/test_benchmarks.py`
- Create: `tests/advisory_r_campaign/test_event_identity.py`
- Modify: `alphapilot/advisory_r_campaign/reporting.py`

**Interfaces:**
- Produces: benchmark comparison, semantic-overlap audit, complete event schema, and independent parity reports.

- [ ] Add RED tests for the ten frozen benchmark names and same-cost/same-timing behavior.
- [ ] Add RED tests for event and exit-leg identity, missing/extra detection, and funding null preservation.
- [ ] Implement benchmark and novelty compilers without adding a new hard gate.
- [ ] Implement event schema validation and independent formal-engine parity.
- [ ] Run benchmark, identity, and reporting tests.
- [ ] Commit `Add corrected benchmark novelty and event parity evidence`.

### Task 5: Commit Code and Freeze the Correction Preregistration

**Files:**
- Modify: `alphapilot/advisory_r_campaign/preregistration.py`
- Create: `research/preregistrations/<correctionCampaignId>.json`
- Create: `tests/advisory_r_campaign/test_correction_preregistration.py`

**Interfaces:**
- Produces: immutable correction campaign identity bound to the committed repair code and compiler hashes.

- [ ] Verify tests, compileall, config validation, safety scan, and diff check.
- [ ] Commit and push all repair code before freezing results.
- [ ] Generate a preregistration with original V15 hash, code commit, and compiler hashes.
- [ ] Assert candidate/parameter/gate/universe/cost changes are all zero.
- [ ] Commit and push `Freeze corrected campaign with unchanged candidate parameters`.

### Task 6: Run One Corrected Prefilter and Package Evidence

**Files:**
- Modify: `alphapilot/advisory_r_campaign/reporting.py`
- Create: `reports/advisory_r_campaign/<correctionCampaignId>/*`

**Interfaces:**
- Produces: the complete V13.27.1.16 report set and a stop-or-next-version route decision.

- [ ] Resolve the frozen snapshot data root and verify all referenced SHA-256 values.
- [ ] Run the correction campaign exactly once.
- [ ] Append the correction attempt without deleting V15 trials.
- [ ] Generate conformance, parity, benchmarks, gates, attribution, comparison, summary, and artifact manifest reports.
- [ ] Assert V15 original hash mismatch count is zero.
- [ ] Assert Locked OOS access, formal evidence, Release, ARM, and order counts are zero.
- [ ] Commit `Run corrected bounded prefilter and record routing decision`.

### Task 7: Documentation, Full Validation, Tags, and Push

**Files:**
- Modify: `README.md`
- Create: `docs/V13.27.1.16-advisory-r-campaign-conformance-repair.md`
- Add the supplied prompt to the Docs repository.

**Interfaces:**
- Produces: reproducible commands, final conclusions, commit/tag references, and known limitations.

- [ ] Run targeted tests, full tests, compileall, validate_config, safety scan, and `git diff --check`.
- [ ] Verify all worktrees are clean and upstream commits match.
- [ ] Tag Quant `v13.27.1.16` and Docs `v13.27.1.16-docs` only after validation.
- [ ] Push branches and tags.
- [ ] Record the exact correction campaign result and next route without claiming profitability.

