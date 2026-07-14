# Archived Failed Strategy Analysis Implementation Plan

> **Execution note:** This is a report-only research task. It reads existing local evidence and must not edit strategies, tune parameters, run backtests, call exchange APIs, or change Demo/Live state.

**Goal:** Turn archived and failed AlphaPilot strategy evidence into an auditable inventory, normalized metrics matrix, failure attribution, negative research rules, reusable components, and bounded revival criteria.

**Architecture:** A deterministic inventory loader reads known status archives and their referenced reports. A null-preserving normalization layer maps heterogeneous evidence to one schema. A separate attribution module evaluates signal edge, account/risk behavior, costs, concentration, exits, data quality, and runtime evidence without inventing missing observations. The command-line generator writes JSON, CSV, Markdown, and supporting documentation from those in-memory records.

**Tech Stack:** Python 3.11+, standard library (`json`, `csv`, `pathlib`, `dataclasses`), pytest, PowerShell safety checks.

---

## Task 1: Lock the analysis contract with tests

**Files:**
- Create: `tests/reports/test_archived_strategy_failure_analysis.py`
- Create: `alphapilot/reports/archived_strategy_failure_analysis_schema.py`

1. Add failing tests for archive discovery, evidence levels, null-preserving metrics, failure categories, and deterministic report outputs.
2. Run the focused test and confirm RED because the new modules do not exist.
3. Add only the schema/constants needed by subsequent implementation.

## Task 2: Build deterministic inventory and normalization

**Files:**
- Create: `alphapilot/reports/archived_strategy_inventory.py`
- Create: `alphapilot/reports/signal_level_failure_attribution.py`
- Modify: `tests/reports/test_archived_strategy_failure_analysis.py`

1. Discover records from explicit local status archives and referenced reports.
2. Normalize identity, scope, status, source, evidence level, headline metrics, and breakdowns.
3. Preserve unavailable values as `None`; never translate missing data to numeric zero.
4. Separate signal-edge findings from account/risk-model findings.
5. Run focused tests and confirm GREEN.

## Task 3: Generate the research artifacts

**Files:**
- Create: `alphapilot/reports/generate_archived_strategy_failure_analysis.py`
- Create: `reports/archived_failed_strategy_inventory.json`
- Create: `reports/archived_failed_strategy_metrics_matrix.json`
- Create: `reports/archived_failed_strategy_failure_attribution.json`
- Create: `reports/archived_failed_strategy_failure_attribution_summary.md`
- Create: `reports/archived_failed_strategy_negative_rules.json`
- Create: `reports/archived_failed_strategy_reusable_components.json`
- Create: `reports/archived_failed_strategy_revival_candidates.json`
- Create: `reports/archived_failed_strategy_metrics_matrix.csv`
- Create: `reports/archived_failed_strategy_failure_attribution.csv`

1. Build primary/secondary failure labels and severity from observed metrics only.
2. Aggregate cross-strategy patterns without promoting correlation to causation.
3. Generate negative rules, reusable components, and bounded revival criteria.
4. Write deterministic JSON/CSV and a concise Chinese Markdown summary.
5. Run the generator twice and assert stable content except `generatedAt` if present.

## Task 4: Document methodology and code navigation

**Files:**
- Create: `docs/archived-failed-strategy-analysis.md`
- Create: `docs/failure-attribution-methodology.md`
- Create: `docs/signal-edge-vs-risk-model-failure.md`
- Create: `docs/negative-research-rules.md`
- Create: `docs/strategy-revival-policy.md`
- Modify: `README.md`
- Modify in Docs repository: `README.md`
- Create in Docs repository: `research/archived-failed-strategy-analysis.md`

1. Explain evidence levels, null semantics, attribution limits, and revival boundaries.
2. State clearly that archived strategies are research assets, not executable candidates.
3. Add exact generator and output paths to both repository navigation docs.

## Task 5: Verify and publish

1. Run `python -m compileall alphapilot`.
2. Run `python -m alphapilot.reports.generate_archived_strategy_failure_analysis`.
3. Run focused and full report tests.
4. Run `python -m alphapilot.scripts.validate_config`.
5. Run `scripts/check_safety.ps1`.
6. Run `git diff --check` in Quant and Docs.
7. Review generated artifacts for credential strings and trade-execution additions.
8. Commit Quant and Docs separately, merge the isolated Quant branch into `main`, and push both repositories.
