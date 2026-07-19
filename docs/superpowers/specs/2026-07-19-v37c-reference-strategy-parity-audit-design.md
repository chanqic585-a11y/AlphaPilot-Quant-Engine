# V37C Reference Strategy Reproduction and Parity Audit

## Status

- Version: V13.27.1.37C
- Scope: audit-only correction after V37B
- Parent evidence commit: `c2743a39cc3cd55cf180385fb904f8032124f6e5`
- Safety: offline, no data download, no Demo/Live mutation, no release creation

## Problem

V37B tested four directional variants derived from two reference-strategy parents and produced no base or formal survivor. That result alone cannot answer whether the external strategies are invalid because three different questions were mixed together:

1. Did the package faithfully reproduce the original source strategy?
2. Did AlphaPilot faithfully execute the package's frozen normalized rules?
3. Do those normalized rules retain economic value in the registered AlphaPilot data and gates?

The existing campaign also masks an out-of-sample failure label whenever Freqtrade translation was not executed. This makes the failure attribution incomplete even though the numeric OOS evidence is present.

## Decision

Build an independent reproduction and parity audit before testing more variants.

The audit separates three identities:

- **Source identity**: original MQL or price-action documentation.
- **Normalized hypothesis identity**: candidate definitions frozen in the supplied package and V37B.
- **Executable identity**: AlphaPilot signal and exit implementation.

V37C does not claim source equivalence unless the source semantics and executable rules match. A clean-room research interpretation remains a new hypothesis even when inspired by a strategy used elsewhere.

## Alternatives Considered

### Lower the gates and rerun

Rejected. It cannot distinguish a translation defect from weak economics and would create result-driven gate changes.

### Assume the external source is correct and optimize the port

Rejected. The UTC source is an FX pending-order EA with broker-time, pip, spread, OCO, break-even and trailing semantics. The V37B candidate is a crypto close-confirmed, next-bar-open normalized hypothesis. The second-entry source is qualitative and discretionary, while V37B freezes numeric ATR and window choices.

### Independent parity audit

Selected. It can prove implementation correctness without pretending that a normalized research variant is the original strategy.

## Source Semantic Findings To Verify

### UTC range strategy

- Original source hash: `b96b8045487ff67de9a9bfe44771975eeb3d87d24541ef8e7f33158505c119e5`.
- Original implementation is MetaTrader/FX-specific and uses pending buy-stop and sell-stop orders.
- Original defaults include broker-time and pip-based parameters, a two-bar lookback, break-even and trailing behavior.
- V37B freezes a 1H crypto hypothesis with four completed bars, UTC anchor 00:00, ATR width filters, close confirmation and next-bar-open execution.
- Required classification: `not_source_equivalent`; V37B is a `clean_room_research_variant`.

### Price-action second-entry strategy

- Source documents describe contextual patterns and discretionary confirmation.
- The package freezes one deterministic interpretation with a 20-bar boundary, two-bar failure window, six-bar retest window and ATR-based tolerances.
- Required classification: `deterministic_normalization_only`; it is not a literal reproduction of a single source algorithm.

### External-use claim

Source availability or third-party use is not audited performance evidence. Without verified fills, comparable cost assumptions, market, timeframe, date range and risk controls, classify the claim as `insufficient_evidence`, not as proof of profitability.

## Architecture

### 1. Source semantics audit

Add `alphapilot/reference_strategy_research/source_semantics.py`.

Responsibilities:

- verify package and selected-source hashes;
- record only bounded metadata, semantic summaries and source citations;
- compare source mechanics with package/V37B normalized mechanics;
- emit an explicit equivalence classification and material gaps;
- never copy large source passages or execute source code.

### 2. Public production signal detector

Add a public detector to `signals.py` that returns pre-exit signal fingerprints:

- signal position and timestamp;
- next-bar entry position and timestamp;
- entry price;
- risk distance.

The event replay will consume this detector so parity checks cover the same production path used by V37B.

### 3. Independent oracle

Add `alphapilot/reference_strategy_research/parity_audit.py`.

The oracle independently re-implements the frozen candidate definitions and must not import private production signal helpers. It compares production and oracle fingerprints on:

- deterministic known-positive synthetic fixtures for both mechanisms and directions;
- one registered BTC 1H partition;
- one registered BTC 4H partition.

Parity requires equal signal count, positions, timestamps and numerically equivalent entry/risk values.

This proves execution parity for V37B rules. It does not prove source equivalence or profitability.

### 4. Gate reachability

Build a deterministic positive event set that satisfies the unchanged preregistered gates. Evaluate it through `evaluate_candidate_gates` and record the result. This demonstrates that zero V37B survivors were not caused by an impossible gate implementation.

### 5. Failure attribution correction

When a candidate passed prescreen but failed base OOS gates, report `out_of_sample_failed` regardless of whether translation was executed. Continue to report `freqtrade_translation_not_executed` separately.

Campaign candidate rows will expose:

- `economicBasePassed`: raw research-gate result;
- `basePassed`: unchanged end-to-end result requiring translation.

No existing artifact is rewritten.

### 6. Audit runner and artifacts

Add `alphapilot/scripts/run_v37c_reference_strategy_parity_audit.py`.

The runner verifies frozen V37B inputs and writes to:

`reports/backtest_screening/reference_strategy_parity/<runId>/`

Artifacts:

- `source_lineage_audit.json`
- `translation_gap_matrix.csv`
- `signal_parity_report.json`
- `gate_reachability_report.json`
- `v37b_reassessment.json`
- `final_conclusion.md`
- `artifact_manifest.json`

## Data Boundary

The real-data parity fixture reuses the V37B catalog only. Its current provenance is `user_confirmed_local_history`, `unverified_local_exchange`, `isProxy=true`, and `isPointInTime=false`. Therefore it can support bounded implementation parity and research reassessment, not formal OKX source replication.

## Acceptance Criteria

1. Package and V37B evidence hashes are verified before analysis.
2. Source equivalence and executable parity are reported separately.
3. Independent oracle parity passes on synthetic and registered real fixtures.
4. Gate reachability passes without changing any gate threshold.
5. OOS failure is no longer hidden by missing translation.
6. V37B artifacts remain byte-for-byte unchanged.
7. The conclusion does not force a winner or claim external profitability.
8. Targeted and full tests pass.
9. `compileall`, safety checks and `git diff --check` pass.
10. No network download, Demo/Live mutation, API credential handling or order creation occurs.

## Expected Interpretation

If parity passes and gate reachability passes, V37B's negative economic result remains valid for the frozen normalized candidates. It still does not establish that the original external strategies fail. A future source-faithful campaign must freeze exact source semantics, market translation assumptions and execution differences before reading results.
