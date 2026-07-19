# V37B Reference Strategy Package Research Design

## Status

- Version: `V13.27.1.37B`
- Date: `2026-07-19`
- Scope: offline research only
- Predecessor: V37A funding data capability commit `4f91c056b12e22b3d523d4bd8250c05847cf8449`

## Objective

Turn the supplied reference-strategy ZIP into a bounded, auditable AlphaPilot research campaign without executing or copying third-party trading code. The package is a hypothesis source, not performance evidence. The workflow must be resumable, must reuse verified local datasets first, and must allow zero survivors.

## Source Boundary

The workflow reads the ZIP in place and verifies:

- archive SHA-256;
- package manifest and per-file hashes;
- candidate-spec schema and candidate hashes;
- absence of executable import or runtime loading.

MQL/EX4/EX5 material is never executed, compiled, imported, or copied into AlphaPilot. Only normalized candidate metadata and concise provenance are retained. Source text is not reproduced.

## Inventory And Dedupe

All 18 package candidates enter `candidate_inventory.json`. Each receives one disposition:

- `selected_bounded_research`;
- `duplicate_existing`;
- `diagnostic_only`;
- `forward_data_required`;
- `research_later`;
- `rejected_policy`;
- `insufficient_evidence`.

Semantic dedupe uses family, mechanism, timeframe, direction, entry timing, stop geometry, and exit policy. Name differences alone never create a new experiment.

The Turtle/Donchian candidates are duplicates of the existing canonical `crypto_tsmom_turtle_v1` family and are not rerun. Broad UTC session predictability already exists, but the package's frozen pre-session range breakout is a materially different event definition and remains eligible. The breakout-failure candidate remains eligible only because it requires a causal second failed test rather than an immediate fade.

## First Bounded Campaign

Only two parent candidates are admitted in the first campaign:

1. `ref_utc_session_range_breakout_1h_v1`, frozen at the `00:00 UTC` anchor, expanded into long and short directional candidates.
2. `ref_pa_breakout_failure_second_entry_4h_v1`, expanded into long and short directional candidates.

The `08:00 UTC` anchor and all other package candidates remain inventory-only. They cannot be promoted because the first campaign fails or produces zero survivors.

Every signal uses completed bars and enters at the following bar open. Initial stops are frozen and may never widen. Exit policies are Advisory-R and are preregistered; no fixed 2R pass gate is introduced.

## Data Policy

The workflow reads `reports/backtest_screening/data_readiness/dataset_catalog.json` and verifies content hashes before use.

Data resolution order:

1. verified catalog dataset;
2. verified reusable local dataset already present under the governed data layer;
3. gap-only public download when a required symbol/timeframe is absent or stale;
4. block the affected candidate when the bounded download budget is exhausted.

The first campaign requires only existing `1h` and `4h` OHLCV for the frozen eight-instrument universe. It must therefore report `downloadRequired=false` and perform no network request.

Future gap collection is bounded by an explicit symbol/timeframe manifest, maximum bytes, maximum requests, retry limit, and minimum free-disk threshold. It may never redownload a verified content hash merely because a new candidate references the same timeframe.

## Workflow State

The long workflow is a deterministic state machine:

1. `source_verified`
2. `inventory_written`
3. `dedupe_complete`
4. `data_audit_complete`
5. `implementation_verified`
6. `preregistered`
7. `campaign_running`
8. `campaign_complete`
9. `closeout_complete`

State is written atomically under `reports/reference_strategy_research/<runId>/workflow_state.json`. A restart resumes from the first incomplete state after verifying all prior artifact hashes. A completed or immutable step is never silently overwritten.

## Campaign Evidence

The workflow must produce:

- `source_verification.json`;
- `candidate_inventory.json`;
- `semantic_dedupe_matrix.csv`;
- `data_gap_audit.json`;
- `selected_candidates.json`;
- immutable preregistration;
- campaign summary JSON and Markdown;
- candidate results Parquet;
- gate matrix;
- failure attribution;
- experiment budget ledger;
- artifact manifest;
- workflow state and closeout Markdown.

## Stop Conditions

The workflow stops safely when:

- package verification fails;
- a selected candidate cannot be normalized deterministically;
- required verified data is unavailable after the bounded gap budget;
- source/code/data hashes drift after preregistration;
- the experiment budget is exhausted;
- all candidates fail prescreen or formal gates.

Zero survivors is a valid completed result. Parameters, candidates, costs, splits, holdout, and gates are not changed to manufacture a pass.

## Safety Boundary

This work has no exchange credential input, private API, order creation, Demo release, live release, or automated promotion. It does not alter immutable releases. Any future Demo admission requires a separate approved evidence handoff after this workflow completes.
