# V37B Reference Strategy Package Research Implementation Plan

## Goal

Implement and run a bounded, resumable research campaign for the supplied reference-strategy package while preserving AlphaPilot's preregistration, locked-OOS, provenance, experiment-budget, and immutable-release boundaries.

## Phase 1: Package Contract And Inventory

1. Add failing tests for archive/manifest verification, candidate hash verification, and executable-source non-import.
2. Implement a read-only ZIP loader that returns normalized metadata without extracting source files.
3. Add an inventory classifier for all 18 candidates.
4. Add semantic fingerprints and explicit duplicate decisions for existing Turtle and related families.

## Phase 2: Candidate Normalization

1. Add failing tests for causal session-range and second-entry signal definitions.
2. Normalize only the two approved parent candidates.
3. Expand each parent into long and short immutable `CandidateSpec` definitions.
4. Implement exact next-bar entry, frozen initial stop, and preregistered Advisory-R exits.
5. Add look-ahead and one-bar perturbation tests.

## Phase 3: Data Audit And Gap-Only Collection

1. Add failing tests that existing 1h/4h catalog rows produce no download plan.
2. Implement hash-verified requirement matching and a deterministic gap manifest.
3. Add a bounded downloader interface with dry-run default, explicit byte/request/free-space limits, and checkpointed progress.
4. Reuse a verified symbol/timeframe dataset across every compatible candidate.

## Phase 4: Resumable Campaign

1. Add workflow-state tests for resume, immutable completed steps, and hash drift.
2. Create source verification, inventory, dedupe, data audit, selected-candidate and preregistration artifacts.
3. Reuse the existing campaign metrics and gate contracts for the four directional candidates.
4. Run selection and locked holdout only according to the frozen campaign contract.
5. Produce failure attribution and accept zero survivors.

## Phase 5: Verification And Delivery

1. Run focused tests, full tests, compileall, config validation, safety scan, and `git diff --check`.
2. Confirm no network call occurred when the data audit reports no gaps.
3. Confirm no Demo/live artifact or order side effect exists.
4. Commit implementation before freezing result-run provenance, then commit generated preregistration and evidence separately.
5. Push the V37B branch and report commits, artifacts, survivors, failures, and remaining data gaps.

## Execution Budget

- Imported metadata: 18 candidates.
- Selected parent candidates: 2.
- Directional candidates: 4.
- Initial parameter variants: 1 per directional candidate.
- Network downloads in the first campaign: 0 expected.
- Structural revisions in this run: 0.
- Forced winners: prohibited.
