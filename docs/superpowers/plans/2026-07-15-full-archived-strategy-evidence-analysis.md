# Full Archived Strategy Evidence Analysis Implementation Plan

> **For Codex:** Execute this plan as a report-only change. Do not rerun backtests, download data, mutate strategy versions, or change Demo/Live state.

**Goal:** Build an auditable, full-coverage archive report across the evolution registry, legacy Freqtrade artifacts, status archives, and existing research reports.

**Architecture:** Use `evolution_registry.sqlite` as the primary identity and lifecycle source. Index legacy Freqtrade ZIP/meta pairs as level-1 evidence, registry workflow JSON as level-2 evidence, and summaries/code as lower evidence. Normalize metrics without inventing missing values, extract compact trade-level rows from one primary artifact per legacy strategy/timeframe, then produce cross-strategy attribution and Chinese reports.

**Tech Stack:** Python standard library, SQLite read-only URI, `zipfile`, `csv`, `json`, `unittest`.

---

### Task 1: Lock report contracts with tests

**Files:**
- Create: `tests/reports/test_full_archived_strategy_analysis.py`

1. Add fixtures for a registry version, one Freqtrade artifact, and one evidence-only strategy.
2. Assert identity provenance, evidence levels, missing-value semantics, trade R/MFE/MAE, failure attribution, and exact output manifest.
3. Run the test and confirm it fails because the new modules do not exist.

### Task 2: Implement discovery and evidence indexing

**Files:**
- Create: `alphapilot/reports/archived_strategy_failure_schema_v2.py`
- Create: `alphapilot/reports/full_archived_strategy_inventory.py`
- Create: `alphapilot/reports/archived_strategy_evidence_index.py`

1. Read registry tables through SQLite read-only mode.
2. Discover legacy strategy classes, meta/ZIP artifacts, old inventory aliases, and indexed reports.
3. Preserve ambiguous identities and evidence conflicts rather than guessing.
4. Hash linked evidence and score completeness.

### Task 3: Implement trade and metric normalization

**Files:**
- Create: `alphapilot/reports/archived_strategy_trade_extractor.py`
- Create: `alphapilot/reports/archived_strategy_metrics_normalizer.py`

1. Select one primary ZIP per legacy strategy/timeframe to prevent duplicate-run inflation.
2. Stream compact trade rows with approximate net R, MFE R, MAE R, costs, tags, pair, time, direction, and exit reason.
3. Normalize registry and Freqtrade metrics with `None` for unavailable evidence.

### Task 4: Implement attribution and orchestration

**Files:**
- Create: `alphapilot/reports/archived_strategy_failure_attribution_v2.py`
- Create: `alphapilot/reports/generate_full_archived_strategy_analysis.py`

1. Separate signal edge, cost, account risk, concentration, stability, zero-trade, evidence, and engineering failures.
2. Assign Chinese labels, severity, confidence, evidence basis, and non-causal limitations.
3. Generate all JSON/CSV/JSONL/Markdown outputs and per-strategy documents.

### Task 5: Persist principles and validate

**Files:**
- Create: `D:/Codex-Workspace/AlphaPilot-Docs/architecture/AlphaPilot_Strategy_Generation_Core_Principles.md`
- Copy: `D:/Codex-Workspace/AlphaPilot-Docs/prompts/AlphaPilot_Full_Archived_Strategy_Evidence_Analysis_Codex_Prompt_CN.md`
- Update: `D:/Codex-Workspace/AlphaPilot-Docs/README.md`
- Create: `D:/Codex-Workspace/memories/extensions/ad_hoc/notes/2026-07-15-alphapilot-strategy-generation-core-principles.md`

1. Run unit tests and the generator.
2. Run compileall, config validation, safety scan, and `git diff --check`.
3. Commit only new full-analysis outputs and source changes; keep the pre-existing modified legacy summary unstaged.
4. Push Quant and Docs repositories.
