# V18.3 Fold Disposition and Ranking Evidence Closure

## Decision

- Campaign: `advisory_r_v18_3_s01_fold_ranking_evidence_correction_aa74e9a2bff29616`
- Candidate: `s01_bear_idiosyncratic_selloff_recovery_4h`
- Route: `archive_s01_current_version`
- Formal pass: no
- Primary blocker: `capital_infeasible_under_frozen_policy`
- Failure class: strategy performance, not implementation or evidence integrity
- Result-driven repair in this campaign: prohibited

V18.3 closes the two V18.2 implementation gaps without changing the frozen strategy or research policy. Every raw event has exactly one disposition, every event assigned to a validation fold has an immutable ranking-evidence record, and the full evidence chain is conserved. The corrected implementation therefore permits a valid economic conclusion: the current S01 version admits zero trades under the frozen policy and must be archived.

## Frozen Scope

No value or ordering changed in the strategy definition, ExitPolicy, capital, capacity, cluster, beta, ranking policy, universe, split, purge, embargo, cost, funding, benchmark, statistical method, or gate threshold. Locked OOS content was not read.

## Structural Certification

- Real raw signal events: 924
- Assigned validation events: 418
- Explicit exclusions: 506
- Unclassified / multi-assigned / cross-boundary leakage: 0 / 0 / 0
- Ranking records: 418 of 418
- Record coverage / status coverage / parity: 100% / 100% / 100%
- Ranking records explicitly unavailable: 418
- Post-entry data reads: 0
- Economic reads / exit replays / result writes: 0 / 0 / 0
- Formal claims / Locked OOS reads: 0 / 0
- Certification: `certified`

The structural certification stopped before capital, PnL, exits, and result writing. It did not count as a formal or economic trial.

## Formal Result

- Claim / attempt / result / read: 1 / 1 / 1 / 1
- Raw events: 884
- Assigned validation events: 417
- Explicit exclusions: 467
- Disposition conservation: exact
- Assigned events with ranking record: 417 of 417
- Available / explicitly unavailable ranking records: 0 / 417
- Missing ranking records / statuses: 0 / 0
- Ranking parity / post-entry reads: 100% / 0
- Accepted / rejected trades: 0 / 884
- Completed folds: 5
- Formal pass / admission: false / false
- Locked OOS / Formal Evidence / Release / ARM / orders: 0 / 0 / 0 / false / 0

Disposition counts:

- `assigned_validation_fold`: 417
- `excluded_initial_history_prefix`: 466
- `excluded_cross_fold_holding_path`: 1
- All other registered exclusion dispositions: 0

Stable rejection counts:

- `reject_formal_evidence_unavailable`: 467
- `reject_ranking_field_unavailable`: 417

## Gate And Statistical Outcome

Translation, capital parity, disposition completeness, point-in-time completeness, ranking completeness, fold completeness, drawdown, and concentration gates passed. Positive average net R, positive total net R, positive-fold minimum, 1.5x cost return gates, and benchmark-increment gates failed because no trades were admitted. Profit factor was not evaluable because there were no losses or trades.

Newey-West alpha was available over 1,939 daily samples and reported alpha `0.0`, HAC t-statistic `0.0`, and one-sided p-value `0.5`. BH FDR, Deflated Sharpe, PBO, White Reality Check, and SPA remain `unavailable_predeclared`; the required point-in-time ten-candidate return panel was not frozen before results, so no retroactive panel was constructed. Same-exchange funding history was unavailable and was not filled with zero.

## Preserved Fail-Closed Attempts

1. `advisory_r_v18_3_s01_fold_ranking_evidence_correction_a4e3b957c2e75dc2` stopped before formal input read because the structural certification was incorrectly supplied in place of the distinct V18.2 evidence-chain fixture certification.
2. `advisory_r_v18_3_s01_fold_ranking_evidence_correction_8eb5b226cc5e3b8d` stopped before result generation because production ranking rows use `canonicalSignalId` and `exactInstrumentId`, while the helper expected fixture aliases.

Both attempts have Claim/Attempt `1/1`, Result/Read `0/0`, and no Locked OOS, Formal Evidence, Release, ARM, or order activity. Their artifacts remain immutable evidence of fail-closed behavior.

## Validation

- Formal validation tests: 198 passed
- Statistical validation tests: 5 passed
- ExitPolicy tests: 22 passed
- Full suite: 959 passed, 157 subtests passed
- `python -m compileall alphapilot`: passed
- `python -m alphapilot.scripts.validate_config`: passed
- Safety scan: reviewed existing negative and test-context matches; no executable trading capability added
- Formal artifact manifest: 65 entries, 0 hash mismatches
- Formal result folder: 81 files
- `git diff --check`: passed before closeout

## Safety Boundary

No API key persistence, Trade API, Withdraw API, account read, position read, order creation, Demo ARM, Live ARM, or automatic trading capability was added. `liveTradingEnabled`, `tradeApiEnabled`, and `withdrawApiEnabled` remain false.

## Next Research Action

Archive the current S01 version. Any future work must open a new preregistered candidate or data-semantics campaign. Do not patch this campaign based on its result, do not relax frozen gates, and do not infer economic performance from the unavailable ranking fields.
