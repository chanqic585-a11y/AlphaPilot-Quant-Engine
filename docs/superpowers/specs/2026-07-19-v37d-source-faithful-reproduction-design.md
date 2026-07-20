# V37D Source-Faithful Reproduction Design

## Objective

V37D determines whether a reference strategy can be reproduced with its original
semantics before AlphaPilot interprets any backtest result as evidence about the
external strategy. It separates three claims that must not be conflated:

1. the external source strategy;
2. an AlphaPilot normalized research variant;
3. an executable whose behavior has been independently checked.

V37D is an offline research and evidence task. It does not create an immutable
Demo Release, ARM Demo or Live, read private accounts, or create orders.

## Current Evidence

- V37C established exact production-oracle parity for the four V37B directional
  candidates.
- V37C established that the unchanged economic gates are reachable.
- All four V37B normalized candidates failed frozen OOS economics.
- V37C did not establish source equivalence for either parent strategy.
- The MT4 source relies on pending orders, broker time, point/pip semantics,
  spread, order cancellation, break-even, and trailing behavior that V37B does
  not reproduce.
- The price-action source is qualitative documentation. Its boundary, tolerance,
  confirmation, stop, and exit rules are AlphaPilot normalization choices.

Therefore V37B is valid negative evidence for the normalized variants only. It
is not evidence that the original external strategies fail.

## Candidate Status Vocabulary

Every audited candidate receives exactly one source status:

- `source_faithful_ready`: all required source semantics and execution inputs are
  frozen and reproducible.
- `normalization_only`: the candidate is a deterministic AlphaPilot research
  definition, but not an exact reproduction of one external algorithm.
- `insufficient_source_evidence`: source material cannot support an executable,
  source-faithful reproduction.

The audit also reports lifecycle status independently:

- `development_stable`: stable only in development evidence;
- `research_eligible`: eligible for bounded research but not formally passed;
- `formal_pass`: passed the frozen formal validation gates;
- `demo_ready`: has an approved immutable Demo Release.

These dimensions must never be collapsed into one vague "good strategy" count.

## Source-Faithful Admission Contract

A candidate may be `source_faithful_ready` only when all requirements below are
present and hashed:

1. exact source identity and version;
2. instrument and venue semantics;
3. timeframe and session timezone;
4. signal and order lifecycle rules;
5. entry fill model, including pending-order behavior when used;
6. spread, fee, slippage, funding, and point/pip semantics;
7. stop, target, break-even, partial close, trailing, and expiry rules;
8. bounded parameter defaults and allowed variants;
9. sufficient point-in-time data for those semantics;
10. an independent oracle or native-engine parity path.

Missing a material item fails closed. The audit may explain what is missing, but
must not infer, optimize, or silently substitute the missing rule.

## Classification Rules

### MT4 UTC Session Candidate

The package includes MQL source, but its execution environment is not frozen for
crypto reproduction. Broker time, pip/point mapping, pending-stop fills, spread,
and several order-management behaviors are material. Until those are frozen and
reproduced, the candidate is `insufficient_source_evidence` for an exact crypto
reproduction. Its V37B crypto port remains a `normalization_only` research
variant.

### Price-Action Second Entry Candidate

The source is qualitative prose rather than one executable algorithm. The V37B
definition is deterministic and auditable, but it is a `normalization_only`
candidate. It cannot be labeled as an exact reproduction.

## Candidate Count Report

V37D emits a machine-readable candidate status inventory with separate counts
for:

- V36 research-eligible candidates;
- V36 development-stable selections;
- V37B reference directional candidates;
- formal passes;
- immutable releases and Demo-ready candidates.

The report must retain the candidate IDs behind every count.

## R and Exit Policy

R remains the normalized risk unit for comparing outcomes. A fixed 2R target is
not a universal hard admission gate. V37D must report the frozen exit policy and
must not rewrite it after seeing results.

## Outputs

V37D writes a deterministic run directory under:

`reports/backtest_screening/reference_strategy_source_fidelity/<runId>/`

Required artifacts:

- `source_identity_matrix.csv`
- `source_admission.json`
- `normalized_vs_source_comparison.json`
- `candidate_status_inventory.json`
- `reproduction_plan.json`
- `final_conclusion.md`
- `artifact_manifest.json`

The manifest contains SHA-256 hashes for every artifact except itself.

## Safety and Integrity

- No network download.
- No private account read.
- No API credential read or storage.
- No Demo or Live mutation.
- No order creation.
- No gate relaxation or forced winner.
- No V37B or V37C artifact rewrite.
- No large source-code passage copied into generated evidence.
- Incomplete source evidence is reported, not repaired by assumption.

## Acceptance Criteria

1. The two selected reference parent candidates receive deterministic source
   classifications with material gaps and source hashes.
2. No candidate is marked source-faithful when a required semantic field is
   missing.
3. V37B normalized OOS failures remain unchanged and are reported separately
   from source-equivalence status.
4. Candidate counts distinguish research eligibility, development stability,
   formal pass, and Demo readiness.
5. The run is deterministic for the same frozen inputs.
6. Artifact hashes verify.
7. Tests prove fail-closed classification, count accuracy, and no side effects.
8. The full repository test suite passes after the branch has an upstream.
