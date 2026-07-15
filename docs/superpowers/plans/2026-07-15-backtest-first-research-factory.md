# AlphaPilot Backtest-First Research Factory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a finite, preregistered research factory that audits real local data, screens independent market hypotheses cheaply, runs full cost-aware purged walk-forward validation only for survivors, and produces reproducible basic/formal pass decisions without manufacturing a winner.

**Architecture:** Add a `research_screening` orchestration package around existing AlphaPilot validation, cost-stress, walk-forward, multiple-testing, and reporting modules. Every campaign starts from a data audit and immutable preregistration, enforces a hard experiment budget, preserves a locked holdout, and writes hash-addressed reports. A formal pass is evidence for a later Demo release; a basic pass is research-only; a failed bounded campaign is archived with attribution.

**Tech Stack:** Python 3.12, pandas, NumPy, PyArrow, SQLite/JSON artifacts, pytest, existing AlphaPilot validation modules, PowerShell.

## Global Constraints

- Use real data already available under `D:\Codex-Workspace\回测数据` and registered AlphaPilot manifests. Do not silently download replacement data during a result-producing run.
- Missing OHLCV, funding, OI, liquidation, spot/perp, basis, volume, point-in-time universe, or breadth evidence remains null/unavailable.
- Start from a falsifiable market mechanism, not a stack of popular indicators.
- One candidate has one core setup. Parameters are bounded, preregistered, versioned, and hashed.
- Initial target is at least 2R; risk is measured in R; the initial stop is never widened.
- Development is 55%, purged walk-forward is 25%, locked final holdout is 20%, with embargo.
- The locked holdout is never used for parameter choice, candidate rescue, family selection, or threshold adjustment.
- Same-bar stop/target collision resolves stop-first.
- No post-hoc symbol deletion, unlimited search, threshold weakening, synthetic fills, or forced pass.
- Preserve the pre-existing uncommitted `reports/archived_failed_strategy_failure_attribution_summary.md`; do not stage or overwrite it.
- No order placement, Demo credential access, Live, or Withdraw behavior belongs in this repository phase.

---

### Task 1: Define deterministic campaign types and artifact layout

**Files:**
- Create: `alphapilot/research_screening/__init__.py`
- Create: `alphapilot/research_screening/types.py`
- Create: `alphapilot/research_screening/artifact_paths.py`
- Test: `tests/research_screening/test_types.py`
- Test: `tests/research_screening/test_artifact_paths.py`

**Core types:**

```python
@dataclass(frozen=True)
class ExperimentBudget:
    maximumFamilies: int = 8
    maximumInitialVariantsPerFamily: int = 2
    maximumInitialCandidates: int = 16
    maximumStructuralRevisionsPerFamily: int = 1
    maximumFullBacktests: int = 48

@dataclass(frozen=True)
class DataSplitPolicy:
    developmentFraction: float = 0.55
    walkForwardFraction: float = 0.25
    holdoutFraction: float = 0.20
    foldCount: int = 5
    embargoBars: int

@dataclass(frozen=True)
class ScreeningCampaignSpec:
    campaignId: str
    createdAt: str
    hypotheses: tuple[HypothesisSpec, ...]
    dataManifestHash: str
    splitPolicy: DataSplitPolicy
    budget: ExperimentBudget
    costScenarios: tuple[CostScenario, ...]
    thresholds: ThresholdPolicy
```

**Artifact root:** `reports/backtest_screening/<campaignId>/`

- [ ] Write tests for canonical JSON serialization, stable SHA-256, path containment, UTC timestamps, and enum validation.
- [ ] Reject more than eight families, more than two initial variants per family, more than sixteen initial candidates, more than one structural revision, or more than forty-eight full backtests.
- [ ] Reject split fractions not summing to `1.0`, fold count below `5`, missing embargo, and non-positive cost assumptions.
- [ ] Implement hash-addressed artifact paths; never overwrite an artifact with the same identity but different bytes.
- [ ] Run `python -m pytest tests/research_screening/test_types.py tests/research_screening/test_artifact_paths.py -q`; expect all tests to pass.
- [ ] Commit: `git commit -m "Define bounded backtest screening campaign contracts"`.

### Task 2: Audit available research data before selecting families

**Files:**
- Create: `alphapilot/research_screening/data_audit.py`
- Create: `alphapilot/research_screening/data_manifest.py`
- Create: `alphapilot/reports/generate_research_data_audit.py`
- Test: `tests/research_screening/test_data_audit.py`
- Test: `tests/research_screening/test_data_manifest.py`

**Interfaces:**

```python
def audit_research_data(
    roots: Sequence[Path],
    *,
    requiredTimeframes: Sequence[str],
) -> ResearchDataAudit

def build_research_data_manifest(audit: ResearchDataAudit) -> ResearchDataManifest
```

**Audit dimensions:**

```text
OHLCV
funding
open interest
liquidation
spot price
perpetual price
basis
volume
point-in-time universe
market breadth
```

- [ ] Write tests with temporary Parquet/JSON fixtures for available, partial, stale, malformed, duplicate, non-monotonic, gapped, and future-leaking data.
- [ ] Record per source: path, format, symbols, timeframe, first/last timestamp, rows, gaps, duplicates, timezone, source, content hash, and usable families.
- [ ] Do not mark a family testable unless every required evidence dimension has adequate coverage.
- [ ] Require at least three genuinely independent testable families before a campaign may label itself `complete`; otherwise report `insufficient_family_coverage` and stop.
- [ ] Generate `data_audit.json` and `data_manifest.json` from real local data.
- [ ] Run `python -m alphapilot.reports.generate_research_data_audit --data-root "D:\Codex-Workspace\回测数据" --output reports/backtest_screening/data_audit`; expect a real report with no fabricated availability.
- [ ] Run focused tests; expect all to pass.

### Task 3: Define independent hypothesis families

**Files:**
- Create: `alphapilot/research_screening/hypothesis_catalog.py`
- Create: `alphapilot/research_screening/hypothesis_validators.py`
- Test: `tests/research_screening/test_hypothesis_catalog.py`

**Initial eligible mechanisms, chosen only when data audit supports them:**

```text
funding/OI crowding reversal
price/OI continuation
liquidation exhaustion
basis deviation mean reversion
market breadth regime shift
liquid cross-sectional momentum
idiosyncratic shock reversion
volatility compression confirmed by OI/volume
```

- [ ] Write tests that reject duplicate family mechanisms disguised by parameter changes.
- [ ] Require every hypothesis to specify causal rationale, direction, timeframe, entry event, invalidation, initial stop, target >=2R, maximum hold, required data, and expected failure regime.
- [ ] Keep long and short variants explicitly distinct, while counting them against the same family budget when they share a mechanism.
- [ ] Reject plain EMA/RSI/MACD/Bollinger stacking as an independent family unless tied to a distinct preregistered market mechanism.
- [ ] Select no more than eight audit-supported families and no more than two initial variants per family.

### Task 4: Freeze immutable preregistration before results

**Files:**
- Create: `alphapilot/research_screening/preregistration.py`
- Modify: `alphapilot/validation/preregistration.py`
- Create during execution: `research/preregistrations/<campaignId>.json`
- Test: `tests/research_screening/test_preregistration.py`

**Preregistration contains:**

```text
hypotheses and variants
data manifest hash
date range
symbol/universe policy
55/25/20 split boundaries
five folds and embargo
final locked holdout hash
sample thresholds
event prefilter gates
basic/formal gates
base/1.5x/2x costs
experiment budget
stop rules
same-bar policy
2R and stop policy
```

- [ ] Write tests proving canonical bytes verify against the stored hash.
- [ ] Write tests proving any field change after freeze invalidates verification.
- [ ] Write tests proving result artifacts cannot be generated from an uncommitted or unverifiable preregistration.
- [ ] Freeze the real campaign file and commit it before executing event studies: `git commit -m "Preregister bounded market hypothesis campaign"`.
- [ ] Record the preregistration Git commit and file hash in every later artifact.

### Task 5: Implement the cheap event-level prefilter

**Files:**
- Create: `alphapilot/research_screening/event_prefilter.py`
- Create: `alphapilot/research_screening/event_schema.py`
- Create: `alphapilot/research_screening/collision_policy.py`
- Test: `tests/research_screening/test_event_prefilter.py`
- Test: `tests/research_screening/test_collision_policy.py`

**Event fields:**

```text
hypothesisId
familyId
variantId
timestamp
symbol
direction
timeframe
entryReference
stopReference
targetReference
maximumHoldBars
split
foldId
dataHash
grossR
feesR
slippageR
fundingR
spreadProxyR
netR
```

**Prefilter gates:**

```text
development base-cost PF >= 1.08
development average net R >= 0.03
positive development months >= 60%
minimum samples and coverage pass
```

**Preregistered sample minimums:**

```text
5m: >= 600 events, >= 12 months, >= 70% positive development months,
    development 1.5x-cost PF >= 1.03, development 1.5x average net R > 0
15m: >= 300 events and >= 12 months
1h: >= 150 events and >= 12 months
4h: >= 80 events and >= 18 months
1d: >= 40 events and >= 24 months
```

- [ ] Write tests for long/short R math, fees, slippage, funding, spread proxy, missing costs, maximum hold, and deterministic month aggregation.
- [ ] Write a stop-first test for same-bar stop/target collision.
- [ ] Enforce the stricter 5m gates in addition to the general prefilter gates.
- [ ] Save event tables as Parquet plus a JSON manifest; hash both.
- [ ] Stop rejected variants before full strategy generation and record exact failed gates.

### Task 6: Enforce split, purge, embargo, and locked holdout

**Files:**
- Create: `alphapilot/research_screening/splits.py`
- Create: `alphapilot/research_screening/holdout_guard.py`
- Reuse/modify: existing purged walk-forward modules under `alphapilot/validation/`
- Test: `tests/research_screening/test_splits.py`
- Test: `tests/research_screening/test_holdout_guard.py`

- [ ] Write tests for chronological 55/25/20 boundaries, five real folds, overlap purge, embargo, and stable fold IDs.
- [ ] Make holdout access require a one-time final-evaluation context bound to preregistration hash and selected candidate IDs.
- [ ] Log only access metadata and hashes; do not expose holdout metrics to parameter-selection functions.
- [ ] Reject a campaign if a selected parameter, family decision, or structural revision timestamp follows holdout access.
- [ ] Preserve `foldId` and `split` on every event and trade.

### Task 7: Run full backtests and cost stress for survivors only

**Files:**
- Create: `alphapilot/research_screening/full_backtest_runner.py`
- Create: `alphapilot/research_screening/cost_scenarios.py`
- Create: `alphapilot/research_screening/strategy_definition_match.py`
- Reuse: existing Freqtrade/backtest adapters and cost-stress modules
- Test: `tests/research_screening/test_full_backtest_runner.py`
- Test: `tests/research_screening/test_strategy_definition_match.py`

**Cost scenarios:**

```text
base: preregistered fee + slippage + funding + spread proxy
stress_1_5x: every variable execution cost multiplied by 1.5
stress_2x: every variable execution cost multiplied by 2.0
```

- [ ] Write tests proving only prefilter survivors consume a full-backtest budget slot.
- [ ] Verify full strategy signal/stop/target/hold hashes match the event-study definition.
- [ ] Keep missing real cost dimensions explicit and use only the separately labeled preregistered conservative proxy.
- [ ] Run five purged walk-forward folds plus one locked holdout evaluation.
- [ ] Enforce forty-eight full-backtest maximum transactionally so process restart cannot reset it.
- [ ] Store stdout/stderr summaries without credentials or oversized raw dumps.

### Task 8: Add multiple-testing and robustness evidence

**Files:**
- Create: `alphapilot/research_screening/multiple_testing.py`
- Create: `alphapilot/research_screening/robustness.py`
- Reuse: existing Benjamini-Hochberg, DSR, and PBO modules where compatible
- Test: `tests/research_screening/test_multiple_testing.py`
- Test: `tests/research_screening/test_robustness.py`

- [ ] Apply Benjamini-Hochberg FDR across the actual candidate set and preserve raw/adjusted values.
- [ ] Compute Deflated Sharpe and PBO only when their statistical preconditions are met; otherwise store `null` plus a reason.
- [ ] Compute symbol and month positive-contribution concentration without deleting contributors.
- [ ] Report fold dispersion, regime coverage, sample size, and data completeness.
- [ ] Reject NaN/inf as missing evidence, never as a pass.

### Task 9: Implement deterministic basic and formal gates

**Files:**
- Create: `alphapilot/research_screening/gates.py`
- Test: `tests/research_screening/test_gates.py`

**Basic research pass:**

```text
OOS PF >= 1.05
OOS average net R > 0
OOS total net R > 0
maximum drawdown <= 25%
at least 3/5 folds have average net R > 0
base costs included
minimum sample and coverage pass
no look-ahead
```

**Formal pass:**

```text
OOS PF >= 1.15
OOS average net R >= 0.05
OOS total net R > 0
maximum drawdown <= 20%
at least 4/5 folds have average net R > 0
1.5x-cost PF >= 1.05
1.5x-cost average net R > 0
single-symbol positive contribution <= 35%
single-month positive contribution <= 35%
locked holdout untouched before final evaluation
```

- [ ] Write one boundary test per gate at below, equal, and above threshold.
- [ ] Require every gate to return `passed`, `observed`, `required`, `evidenceHash`, and `reasonZh`.
- [ ] Make formal pass imply basic pass, but never infer missing evidence.
- [ ] Ensure 2x stress is reported for diagnosis but does not silently replace preregistered formal gates.

### Task 10: Implement bounded structural revision and stop rules

**Files:**
- Create: `alphapilot/research_screening/experiment_budget.py`
- Create: `alphapilot/research_screening/failure_attribution.py`
- Test: `tests/research_screening/test_experiment_budget.py`
- Test: `tests/research_screening/test_failure_attribution.py`

- [ ] Persist counters for families, variants, revisions, and full backtests so restarts preserve the budget.
- [ ] Permit at most one preregistered structural revision per family; parameter-only copies still count as variants.
- [ ] For each failure, attribute sample, cost, drawdown, fold instability, concentration, data, or mechanism weakness.
- [ ] At budget exhaustion, mark the family/campaign archived and prohibit auto-requeue.
- [ ] Do not edit the locked candidate or revive an archived candidate; a new mechanism requires a new campaign ID.

### Task 11: Build the campaign runner and resume checkpoints

**Files:**
- Create: `alphapilot/research_screening/runner.py`
- Create: `alphapilot/research_screening/checkpoint_store.py`
- Create: `alphapilot/scripts/run_backtest_screening.py`
- Create: `scripts/run_backtest_screening.ps1`
- Test: `tests/research_screening/test_runner.py`
- Test: `tests/research_screening/test_checkpoint_store.py`

**CLI:**

```powershell
python -m alphapilot.scripts.run_backtest_screening `
  --preregistration research/preregistrations/<campaignId>.json `
  --data-root "D:\Codex-Workspace\回测数据" `
  --resume
```

- [ ] Write crash/restart tests for every phase: audit, prefilter, full backtest, robustness, holdout, and reporting.
- [ ] Use atomic checkpoints keyed by campaign, candidate, definition hash, data hash, and phase.
- [ ] On resume, verify all upstream hashes before reusing artifacts; invalidate only the affected downstream task.
- [ ] Allow bounded worker parallelism for independent candidates while serializing budget and holdout access.
- [ ] Never run a network downloader from this runner.

### Task 12: Generate auditable reports and the read projection

**Files:**
- Create: `alphapilot/research_screening/reporting.py`
- Create: `alphapilot/reports/generate_backtest_screening_report.py`
- Create: `reports/backtest_screening/.gitkeep`
- Test: `tests/research_screening/test_reporting.py`

**Report outputs:**

```text
campaign_summary.json
campaign_summary.md
candidate_results.parquet
gate_matrix.json
failure_attribution.json
experiment_budget.json
artifact_manifest.json
```

- [ ] Test deterministic report generation from fixed fixtures.
- [ ] Include data/preregistration/code/cost/strategy hashes, budget counters, all trial IDs, FDR, fold details, concentration, and null reasons.
- [ ] Rank by formal status, OOS PF, average net R, 1.5x PF, positive-fold ratio, drawdown, concentration, sample size, and evidence completeness; not raw return alone.
- [ ] Produce a compact projection JSON suitable for Console `GET /api/backtest-screening`.
- [ ] Label results `historical_backtest`; never label them forward, Demo, Live, or guaranteed.

### Task 13: Execute one real bounded campaign

**Files:**
- Create before results: `research/preregistrations/<campaignId>.json`
- Create after results: `reports/backtest_screening/<campaignId>/*`
- Modify: `README.md`
- Create: `docs/backtest-first-research-factory.md`

- [ ] Run the real data audit and select only audit-supported families.
- [ ] Freeze and commit the preregistration before reading screening results.
- [ ] Run the campaign with `--resume` and preserve all failed trials.
- [ ] Confirm initial candidates `<=16`, full backtests `<=48`, and structural revisions `<=1` per family.
- [ ] Confirm the final holdout was accessed only after candidate selection was frozen.
- [ ] Accept zero formal passes as a valid completed campaign.
- [ ] If there are formal passes, emit only the formal-pass evidence bundle; do not create or approve a Demo release in this phase.

### Task 14: Phase 3 verification and commit hygiene

- [ ] Run `python -m pytest tests/research_screening -q`.
- [ ] Run `python -m pytest tests -q`.
- [ ] Run `python -m compileall alphapilot`.
- [ ] Run `python -m alphapilot.scripts.validate_config`.
- [ ] Run `powershell -ExecutionPolicy Bypass -File scripts\check_safety.ps1`.
- [ ] Run `git diff --check`.
- [ ] Scan for holdout metrics referenced by selection code, unbounded loops, dynamic threshold reduction, downloader invocation, order API, credentials, Withdraw, and Live activation.
- [ ] Verify every report artifact against `artifact_manifest.json` hashes.
- [ ] Stage only intended code, docs, preregistration, and bounded report manifests; do not stage the pre-existing archived-failure report.
- [ ] Commit implementation: `git commit -m "Build bounded backtest-first research factory"`.
- [ ] Commit result manifests separately: `git commit -m "Record preregistered backtest screening campaign"`.
- [ ] Push and require intended scope clean before Phase 4.

## Phase Exit Gate

Phase 3 passes only when a real bounded campaign completes from an immutable preregistration, all five purged folds and cost scenarios are evidenced, holdout access is isolated, FDR is reported, experiment counters remain within limits, and every result is reproducible from hashes. Zero formal passes is an acceptable phase result and must not trigger weaker gates or extra trials.
