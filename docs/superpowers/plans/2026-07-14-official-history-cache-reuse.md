# Official History Cache Reuse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse every compatible completed OKX official OHLCV partition across strategies and persist partial downloads so only missing history is fetched for `5m`, `15m`, `1h`, `4h`, and `1d`.

**Architecture:** Build one lazy-validating manifest index per collector run, keyed by instrument, timeframe, and endpoint. Add a temporary resumable chunk store keyed by data contract and partition; the collector resumes OKX pagination from the oldest durable cursor and merges chunks once on completion.

**Tech Stack:** Python 3.12, pandas/Parquet, atomic JSON checkpoints, unittest/pytest.

## Global Constraints

- Do not alter strategy logic, target R, backtest gates, universe ranking, Demo execution, or Live boundaries.
- Only hash-verified canonical files with OKX official manifests count as formal evidence.
- Do not relabel local or third-party research files as official.
- Do not stop or restart the currently running external batch worker.
- Use `D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe` for validation.

---

### Task 1: Index Completed Official Partitions Once

**Files:**
- Create: `alphapilot/data_foundation/official_partition_index.py`
- Test: `tests/data_foundation/test_official_partition_index.py`

**Interfaces:**
- Produces: `OfficialPartitionIndex.from_manifests(manifest_root, canonical_root)` and `latest_valid(instrument_id, timeframe, endpoint)`.
- Returns manifest metadata only after path containment, file existence, schema, endpoint, and SHA-256 validation.

- [ ] **Step 1: Write failing tests**

```python
def test_indexes_once_and_returns_latest_valid_partition():
    index = OfficialPartitionIndex.from_manifests(manifest_root, canonical_root)
    assert index.latest_valid("BTC-USDT-SWAP", "5m", endpoint).endTime == latest

def test_skips_wrong_hash_and_outside_canonical_root():
    index = OfficialPartitionIndex.from_manifests(manifest_root, canonical_root)
    assert index.latest_valid("BTC-USDT-SWAP", "5m", endpoint) is None
```

- [ ] **Step 2: Verify RED**

Run: `D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m pytest -q tests/data_foundation/test_official_partition_index.py`

Expected: import failure because `official_partition_index.py` does not exist.

- [ ] **Step 3: Implement the minimal index**

```python
@dataclass(frozen=True)
class IndexedOfficialPartition:
    instrumentId: str
    timeframe: str
    rows: int
    startTime: str
    endTime: str
    outputPath: str
    outputSha256: str
    sourceEndpoint: str

class OfficialPartitionIndex:
    @classmethod
    def from_manifests(cls, manifest_root: Path, canonical_root: Path): ...
    def latest_valid(self, instrument_id: str, timeframe: str, endpoint: str): ...
```

- [ ] **Step 4: Verify GREEN**

Run the focused test and expect all tests to pass.

- [ ] **Step 5: Commit**

Commit message: `feat: index reusable official history partitions`

### Task 2: Persist and Reload Partial Official Downloads

**Files:**
- Create: `alphapilot/data_foundation/official_resume.py`
- Test: `tests/data_foundation/test_official_resume.py`

**Interfaces:**
- Produces: `ResumeIdentity`, `ResumeSnapshot`, and `OfficialResumeStore`.
- `load(identity)` validates metadata and chunk schema, then returns deduplicated rows and the oldest durable cursor.
- `append(identity, frame, request_count, oldest_timestamp_ms)` writes an immutable Parquet chunk and atomic state file.
- `clear(identity)` removes temporary chunks only after formal canonical write succeeds.

- [ ] **Step 1: Write failing tests**

```python
def test_partial_chunks_survive_a_new_store_instance():
    first.append(identity, frame, request_count=25, oldest_timestamp_ms=oldest)
    resumed = OfficialResumeStore(root).load(identity)
    assert len(resumed.frame) == len(frame)
    assert resumed.oldestTimestampMs == oldest

def test_identity_mismatch_does_not_reuse_chunks():
    assert OfficialResumeStore(root).load(changed_identity).frame.empty
```

- [ ] **Step 2: Verify RED**

Run the focused test and expect an import failure.

- [ ] **Step 3: Implement the resumable store**

Use contract/key hashed directories under `_alphapilot/tmp/official-resume`, atomic `state.json`, immutable compressed Parquet chunks, schema validation, and deduplication by `timestamp_ms`.

- [ ] **Step 4: Verify GREEN**

Run the focused test and expect all tests to pass.

- [ ] **Step 5: Commit**

Commit message: `feat: persist partial official history chunks`

### Task 3: Resume OKX Pagination from a Durable Cursor

**Files:**
- Modify: `alphapilot/data_foundation/okx_public.py`
- Modify: `tests/data_foundation/test_okx_public.py`

**Interfaces:**
- Add optional `initial_after_ms: int | None = None` to `history_candles`.
- Add `pageRows` to page progress payloads without changing returned DataFrame columns.

- [ ] **Step 1: Write failing tests**

```python
def test_history_candles_starts_after_resume_cursor():
    client.history_candles(..., initial_after_ms=cursor)
    assert client.requests[0]["after"] == cursor

def test_page_progress_contains_only_confirmed_page_rows():
    assert progress[0]["pageRows"] == expected_confirmed_rows
```

- [ ] **Step 2: Verify RED**

Run the two named tests and verify they fail for the missing parameter/payload.

- [ ] **Step 3: Implement cursor and page payload support**

Initialize `cursor = initial_after_ms`; include only accepted confirmed rows in `pageRows`; preserve current stop behavior and return type.

- [ ] **Step 4: Verify GREEN**

Run `tests/data_foundation/test_okx_public.py` and expect all tests to pass.

- [ ] **Step 5: Commit**

Commit message: `feat: resume OKX history pagination`

### Task 4: Wire Cache-First and Durable Resume into the Collector

**Files:**
- Modify: `alphapilot/data_foundation/official_history.py`
- Modify: `tests/data_foundation/test_official_history.py`

**Interfaces:**
- Collector builds `OfficialPartitionIndex` once at the start of `collect`.
- Collector creates `ResumeIdentity` from contract, key, endpoint, collection start, and shared-base hash.
- Progress callback batches page rows and flushes every 25 requests; pause/error paths flush remaining rows.
- Successful completion merges previous chunks, current rows, and shared base, then clears chunks.

- [ ] **Step 1: Write failing integration tests**

```python
def test_multiple_timeframes_share_one_manifest_index_build(): ...
def test_paused_download_resumes_from_oldest_persisted_cursor(): ...
def test_resume_merges_rows_without_duplicates_and_clears_chunks(): ...
```

- [ ] **Step 2: Verify RED**

Run the three named tests and confirm failures describe repeated indexing or missing durable resume.

- [ ] **Step 3: Implement minimal collector wiring**

Keep exact-contract checkpoint reuse first, then query the shared index, then load partial chunks, fetch only the missing range, write canonical output, and clear temporary chunks only on success.

- [ ] **Step 4: Verify GREEN**

Run `tests/data_foundation/test_official_history.py` and expect all tests to pass.

- [ ] **Step 5: Commit**

Commit message: `fix: reuse and resume official strategy history`

### Task 5: Validate the Complete Data Layer

**Files:**
- Modify: `README.md` only if the current data-warehouse section lacks cache-first semantics.

- [ ] **Step 1: Run focused tests**

Run: `D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m pytest -q tests/data_foundation`

- [ ] **Step 2: Run complete tests**

Run: `D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m pytest -q tests`

- [ ] **Step 3: Compile and whitespace checks**

Run:

```powershell
D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m compileall alphapilot
git diff --check
```

- [ ] **Step 4: Inspect current warehouse without mutating it**

Report Top50 coverage for `5m`, `15m`, `1h`, `4h`, and `1d`, distinguishing completed reusable partitions from missing or partial partitions.

- [ ] **Step 5: Merge the isolated branch without restarting the active worker**

Fast-forward or cherry-pick verified commits into `main`. The running worker keeps its loaded implementation; the next worker invocation uses the new cache-first resume behavior.
