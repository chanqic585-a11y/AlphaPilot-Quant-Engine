# V37D Source-Faithful Reproduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic offline audit that separates source-faithful strategies, normalized research variants, and insufficient source evidence while reporting the current strategy funnel accurately.

**Architecture:** A focused source-fidelity module converts the frozen V37C lineage audit into a fail-closed admission contract. A V37D runner verifies V36/V37B/V37C identities, produces candidate lifecycle counts and comparison artifacts, and writes a hashed evidence bundle without changing prior runs.

**Tech Stack:** Python 3.11+, dataclasses/dicts, `json`, `csv`, `hashlib`, existing AlphaPilot atomic JSON and hashing helpers, pytest.

## Global Constraints

- No network download.
- No Demo or Live mutation, ARM, private account read, credential access, or order creation.
- Do not modify V37B or V37C artifacts.
- Do not relax gates or force a winner.
- R is the comparison unit; fixed 2R is not a universal hard admission gate.
- Missing source semantics fail closed.
- Do not copy large source-code passages into repository evidence.

---

### Task 1: Source-Fidelity Admission Contract

**Files:**
- Create: `tests/reference_strategy_research/test_source_fidelity.py`
- Create: `alphapilot/reference_strategy_research/source_fidelity.py`

**Interfaces:**
- Consumes: one source-lineage candidate row from `source_lineage_audit.json`.
- Produces: `classify_source_candidate(candidate: dict[str, Any]) -> dict[str, Any]` and `build_source_admission(source_audit: dict[str, Any]) -> dict[str, Any]`.

- [ ] **Step 1: Write failing tests for fail-closed classification**

```python
def test_missing_material_requirements_cannot_be_source_faithful() -> None:
    row = {
        "candidateId": "candidate-a",
        "equivalenceStatus": "not_source_equivalent",
        "translationClass": "clean_room_research_variant",
        "materialGaps": ["broker time is not frozen"],
        "sources": [{"path": "strategy.mq4", "sha256": "a" * 64}],
    }
    result = classify_source_candidate(row)
    assert result["sourceStatus"] == "insufficient_source_evidence"
    assert result["sourceFaithfulReady"] is False


def test_documentation_normalization_stays_normalization_only() -> None:
    row = {
        "candidateId": "candidate-b",
        "equivalenceStatus": "deterministic_normalization_only",
        "translationClass": "documentation_normalization",
        "materialGaps": ["source is qualitative prose"],
        "sources": [{"path": "notes.txt", "sha256": "b" * 64}],
    }
    result = classify_source_candidate(row)
    assert result["sourceStatus"] == "normalization_only"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m pytest --import-mode=importlib tests\reference_strategy_research\test_source_fidelity.py -q
```

Expected: collection fails because `source_fidelity` does not exist.

- [ ] **Step 3: Implement the minimal admission classifier**

Implement stable requirement IDs, deterministic ordering, candidate counts, and
the three source statuses from the design. Reject unsupported equivalence values
instead of guessing.

- [ ] **Step 4: Run tests and verify GREEN**

Expected: all tests in `test_source_fidelity.py` pass.

- [ ] **Step 5: Commit**

```powershell
git add alphapilot/reference_strategy_research/source_fidelity.py tests/reference_strategy_research/test_source_fidelity.py
git commit -m "feat: add fail-closed source fidelity admission"
```

### Task 2: Candidate Funnel Inventory

**Files:**
- Modify: `tests/reference_strategy_research/test_source_fidelity.py`
- Modify: `alphapilot/reference_strategy_research/source_fidelity.py`

**Interfaces:**
- Consumes: V36 campaign summary and neighborhood selection, V37B closeout, and V37C reassessment.
- Produces: `build_candidate_status_inventory(...) -> dict[str, Any]`.

- [ ] **Step 1: Write a failing count-separation test**

```python
def test_candidate_inventory_does_not_call_research_candidates_formal_passes() -> None:
    result = build_candidate_status_inventory(
        v36_summary={"eligibleCandidateCount": 6, "stableSelectionCount": 2},
        v36_selection={"selections": [{"candidateId": "stable-a", "eligible": True}]},
        v37b_closeout={"directionalCandidateCount": 4, "demoReleaseCount": 0},
        v37c_reassessment={"candidates": [{"candidateId": "ref-a", "formalPassed": False}]},
    )
    assert result["researchEligibleCount"] == 6
    assert result["developmentStableCount"] == 2
    assert result["formalPassCount"] == 0
    assert result["demoReadyCount"] == 0
```

- [ ] **Step 2: Run the test and verify RED**

Expected: `build_candidate_status_inventory` is missing.

- [ ] **Step 3: Implement deterministic inventory aggregation**

The implementation records IDs when available, preserves aggregate evidence
when the source summary contains more candidates than an ID list, and never
promotes a count across lifecycle stages.

- [ ] **Step 4: Run tests and verify GREEN**

- [ ] **Step 5: Commit**

```powershell
git add alphapilot/reference_strategy_research/source_fidelity.py tests/reference_strategy_research/test_source_fidelity.py
git commit -m "feat: separate AlphaPilot candidate lifecycle counts"
```

### Task 3: Deterministic V37D Evidence Runner

**Files:**
- Create: `tests/reference_strategy_research/test_v37d_runner.py`
- Create: `alphapilot/scripts/run_v37d_source_fidelity_audit.py`

**Interfaces:**
- Consumes: repository root, reference package path, frozen V36/V37B/V37C run directories, optional output root.
- Produces: `run_v37d_source_fidelity_audit(...) -> dict[str, Any]` and seven required evidence files.

- [ ] **Step 1: Write a failing end-to-end test**

```python
def test_v37d_runner_writes_hashed_fail_closed_bundle(tmp_path: Path) -> None:
    result = run_v37d_source_fidelity_audit(
        repo_root=REPO_ROOT,
        package_path=PACKAGE_PATH,
        v36_run_dir=V36_RUN_DIR,
        v37b_run_dir=V37B_RUN_DIR,
        v37c_run_dir=V37C_RUN_DIR,
        output_root=tmp_path,
    )
    output = Path(result["output"])
    assert result["sourceFaithfulReadyCount"] == 0
    assert result["developmentStableCount"] == 2
    assert result["formalPassCount"] == 0
    assert result["demoReadyCount"] == 0
    assert (output / "source_identity_matrix.csv").is_file()
    assert (output / "artifact_manifest.json").is_file()
```

- [ ] **Step 2: Run the test and verify RED**

Expected: runner module is missing.

- [ ] **Step 3: Implement input verification and artifact generation**

Verify package hash against V37B, recompute source semantics against V37C,
preserve the V37B reassessment unchanged, and write:

```text
source_identity_matrix.csv
source_admission.json
normalized_vs_source_comparison.json
candidate_status_inventory.json
reproduction_plan.json
final_conclusion.md
artifact_manifest.json
```

Use a run ID derived from frozen input hashes. The result status is
`completed_no_source_faithful_candidates` when no exact reproduction is
admissible; this is a successful audit, not a strategy pass.

- [ ] **Step 4: Add side-effect assertions**

The test asserts `networkDownloads == 0`, `demoOrLiveMutations == 0`,
`ordersCreated == 0`, and `forcedWinner is False`.

- [ ] **Step 5: Run targeted tests and verify GREEN**

```powershell
D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m pytest --import-mode=importlib tests\reference_strategy_research\test_source_fidelity.py tests\reference_strategy_research\test_v37d_runner.py -q
```

- [ ] **Step 6: Commit**

```powershell
git add alphapilot/scripts/run_v37d_source_fidelity_audit.py tests/reference_strategy_research/test_v37d_runner.py
git commit -m "feat: add V37D source fidelity evidence runner"
```

### Task 4: Execute V37D and Verify the Repository

**Files:**
- Create: `reports/backtest_screening/reference_strategy_source_fidelity/<runId>/*`

**Interfaces:**
- Consumes: the committed V37D runner and frozen evidence directories.
- Produces: the final V37D evidence bundle and pushed feature branch.

- [ ] **Step 1: Run V37D against frozen inputs**

```powershell
$sourceVerification = Get-Content -Raw -Encoding UTF8 `
  reports\backtest_screening\reference_strategy_research\v37b-reference-c714273e3046-231c239eb744\source_verification.json | ConvertFrom-Json
D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m alphapilot.scripts.run_v37d_source_fidelity_audit `
  --repo D:\Codex-Workspace\AlphaPilot-Quant-V37C-parity-worktree `
  --package $sourceVerification.archivePath `
  --v36-run-dir reports\candidate_research\v36\v36-development-replay-okx-v34c-20260719 `
  --v37b-run-dir reports\backtest_screening\reference_strategy_research\v37b-reference-c714273e3046-231c239eb744 `
  --v37c-run-dir reports\backtest_screening\reference_strategy_parity\v37c-parity-c714273e3046-80dcc774d405
```

Expected: status `completed_no_source_faithful_candidates`, development-stable
count 2, formal-pass count 0, Demo-ready count 0.

- [ ] **Step 2: Verify deterministic rerun**

Run the same command again and confirm the same `runId` and artifact hashes.

- [ ] **Step 3: Run validation**

```powershell
D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m compileall alphapilot
D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m alphapilot.scripts.validate_config
powershell -ExecutionPolicy Bypass -File scripts\check_safety.ps1
D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m pytest --import-mode=importlib tests -q
git diff --check
```

Expected: all checks pass; repository suite reports zero failures.

- [ ] **Step 4: Commit evidence and push**

```powershell
git add reports/backtest_screening/reference_strategy_source_fidelity
git commit -m "research: record V37D source fidelity audit"
git push
```

- [ ] **Step 5: Confirm final status**

Confirm local HEAD equals the upstream branch, `git status --short` is empty,
and no Demo/Live repository was modified.

## Self-Review

- Spec coverage: source status, lifecycle counts, deterministic artifacts,
  fail-closed behavior, R-policy wording, and safety boundaries all have tasks.
- Placeholder scan: no implementation placeholder or unfrozen parameter remains.
- Type consistency: the classifier, inventory builder, and runner signatures are
  defined once and reused consistently.
