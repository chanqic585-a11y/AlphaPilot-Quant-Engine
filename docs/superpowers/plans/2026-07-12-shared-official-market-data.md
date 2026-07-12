# Shared Official Market Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse verified OKX canonical OHLCV across strategy contracts and download only missing tails.

**Architecture:** Add a focused manifest resolver to the official-history collector. Exact checkpoints remain first priority; cross-contract canonical manifests provide a verified base, and the existing OKX client downloads only rows after the base cutoff before normal validation and persistence.

**Tech Stack:** Python 3, pandas, Parquet, JSON manifests, unittest.

## Global Constraints

- Local research smoke stays before formal official collection.
- Formal evidence remains OKX public-only and hash verified.
- One serial workflow batch remains the physical downloader.
- No strategy/risk/promotion rule changes.
- No credentials, private APIs, orders, or Withdraw.

---

### Task 1: Resolve a verified shared canonical base

**Files:**
- Modify: `alphapilot/data_foundation/official_history.py`
- Test: `tests/data_foundation/test_official_history.py`

**Interfaces:**
- Produces: `_shared_partition_base(instrument_id, timeframe, endpoint) -> OfficialPartition | None`
- Validates: manifest identity, canonical-root containment, file existence, and SHA-256.

- [x] Write tests for valid reuse and rejection of hash-mismatched manifests.
- [x] Run the tests and observe the expected failure.
- [x] Implement minimal manifest discovery and deterministic newest-valid selection.
- [x] Run the targeted tests and confirm they pass.
- [x] Commit the resolver and incremental reuse together.

### Task 2: Download only the missing tail

**Files:**
- Modify: `alphapilot/data_foundation/official_history.py`
- Test: `tests/data_foundation/test_official_history.py`

**Interfaces:**
- Consumes: the verified shared canonical base from Task 1.
- Produces: a full validated partition made from base plus confirmed incremental rows, or an unchanged reused partition when the tail is empty.

- [x] Write a test proving `history_candles` receives the base last timestamp instead of the contract start.
- [x] Write a test proving an empty tail reuses the original output hash.
- [x] Run both tests and observe the expected failures.
- [x] Implement base-frame loading, tail merge, reduced page budget, and unchanged-file reuse.
- [x] Run official-history and full Quant tests.
- [x] Commit incremental reuse.

### Task 3: Document, validate, and deploy

**Files:**
- Modify: `README.md`
- Create: `docs/V13.27.8-shared-official-market-data.md`

**Interfaces:**
- Reports the shared-data boundary and selected workflow order.

- [x] Update version documentation without changing strategy definitions.
- [x] Run all Quant unit tests.
- [x] Run compileall, diff check, and changed-line safety scan.
- [x] Fast-forward `main`, push, and verify only one logical workflow worker.
- [x] Confirm selected queue contains only the 5m strategy, 15m strategy, and Alpha191.
