# Bounded Structural Redesign Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically archive a structurally weak research strategy, create one deterministic immutable structural child, and queue it through the existing serial backtest workflow, with a separate maximum of three structural generations.

**Architecture:** Pure domain code builds a split-safe failure profile and selects one allowlisted recipe. A focused workflow repository transaction atomically registers the child, queues its initial run, writes stable audit events, and archives the parent; a recovery command performs an online SQLite backup before replaying terminal historical failures. The existing worker remains the only formal backtest slot, while the Console receives a capability-gated lifecycle projection.

**Tech Stack:** Python 3.11+, frozen dataclasses, SQLite, unittest/pytest, existing AlphaPilot workflow registry, vanilla JavaScript Console UI.

## Global Constraints

- Structural generations are exactly `1`, `2`, and `3`; generation 3 failure stops the campaign.
- Structural generation budget is independent from the existing three bounded parameter attempts.
- Only development and walk-forward evidence may influence recipe selection.
- Holdout and locked-validation metrics must never enter a failure profile, recipe decision, or audit payload.
- `targetR >= 2.0` is immutable; leverage and capital allocation are never mutated.
- Only allowlisted strategy recipes may be generated; no arbitrary Python or executable source generation.
- Data, network, worker, and missing-evidence failures never create a structural child.
- Child registration, queued run, stable audit, and parent archive must commit in one SQLite transaction.
- A failed transaction leaves the parent active and creates no partial child.
- Existing Demo and Live releases remain unchanged.
- Existing formal backtest concurrency remains one worker, with at most one data-prefetch worker.
- No raw API credentials, Withdraw API, or execution permission is added.

---

## File Structure

### Quant Engine

- Create `alphapilot/evolution/workflow/structural_redesign.py`: split-safe failure profile, deterministic recipe grammar, generation budget, and immutable child proposal.
- Create `alphapilot/evolution/workflow/structural_redesign_service.py`: idempotent processing, atomic persistence orchestration, historical recovery, and online backup.
- Modify `alphapilot/evolution/workflow/repository.py`: focused atomic transaction methods for redesign create/stop commits.
- Modify `alphapilot/evolution/workflow/cli.py`: worker hook and `recover-structural-redesigns` command.
- Modify `alphapilot/evolution/workflow/projection.py`: expose `structuralRedesignCampaign` without exposing holdout data.
- Create `tests/evolution/test_structural_redesign.py`: pure domain policy tests.
- Create `tests/evolution/test_structural_redesign_integration.py`: atomicity, idempotency, recovery, and queue-drain tests.
- Modify `tests/evolution/test_workflow_cli.py`: CLI recovery and projection contract tests.
- Modify `README.md`: bounded loop, recovery command, and safety boundary.

### Control Console

- Modify `alphapilot_control_console/workflow_client.py`: allow recovery command and advertise `structuralRedesignRecovery` only when the Quant projection supports it.
- Modify `web/app.js`: render concise Chinese generation, parent, recipe, child, and stop state.
- Modify `tests/test_workflow_client.py`: capability handshake test.
- Modify `tests/test_workflow_ui_contract.py`: Chinese lifecycle contract and capability-gate test.
- Modify `README.md`: describe capability-gated display and unchanged trading boundary.

---

### Task 1: Split-Safe Failure Profile and Controlled Grammar

**Files:**
- Create: `alphapilot/evolution/workflow/structural_redesign.py`
- Test: `tests/evolution/test_structural_redesign.py`

**Interfaces:**
- Consumes: strategy definition/parameters, sanitized metrics from `sanitize_selection_metrics`, gate rules, failure category, and prior lineage recipe IDs.
- Produces: `build_structural_failure_profile(value: StructuralRedesignInput) -> StructuralFailureProfile` and `decide_structural_redesign(value: StructuralRedesignInput) -> StructuralRedesignDecision`.

- [ ] **Step 1: Write failing policy tests**

Add tests that construct development, walk-forward, holdout, and locked metrics and assert:

```python
profile = build_structural_failure_profile(structural_input())
self.assertEqual(set(profile.metricsBySplit), {"development", "walk_forward"})
self.assertNotIn("holdout", repr(profile))
self.assertNotIn("locked", repr(profile))

first = decide_structural_redesign(structural_input())
second = decide_structural_redesign(structural_input())
self.assertEqual(first, second)
self.assertEqual(first.action, "create_child")
self.assertEqual(first.generation, 1)
self.assertGreaterEqual(first.proposedDefinition["targetR"], 2.0)

exhausted = decide_structural_redesign(
    structural_input(lineage_generation=3)
)
self.assertEqual(exhausted.action, "stop")
self.assertEqual(exhausted.reasonCode, "structural_generation_budget_exhausted")
```

Also assert missing walk-forward evidence, non-performance failure, duplicate recipe, and an existing active child return `stop` or `wait` without a proposal.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\evolution\test_structural_redesign.py -q
```

Expected: collection fails because `structural_redesign` does not exist.

- [ ] **Step 3: Implement immutable domain types and profile sanitization**

Implement frozen dataclasses with these exact public fields:

```python
@dataclass(frozen=True)
class StructuralRedesignInput:
    rootStrategyVersionId: str
    currentStrategyVersionId: str
    displayName: str
    definition: dict[str, Any]
    parameters: dict[str, Any]
    metrics: dict[str, Any]
    gateRules: dict[str, Any]
    failureCategory: str | None
    runStatus: str
    usedRecipeIds: tuple[str, ...] = ()
    activeStructuralChildExists: bool = False

@dataclass(frozen=True)
class StructuralFailureProfile:
    failedGateNames: tuple[str, ...]
    metricsBySplit: dict[str, dict[str, Any]]
    costStressBySplit: dict[str, dict[str, Any]]
    direction: str
    timeframe: str
    signalFamily: str
    exitPolicy: str
    currentFilters: dict[str, Any]
    overtrading: bool
    weakExpectancy: bool
    drawdownConcentration: bool
    sparseSample: bool
    transactionCostSensitive: bool
    evidenceHash: str

@dataclass(frozen=True)
class StructuralRedesignDecision:
    action: str
    reasonCode: str
    campaignId: str
    decisionKey: str
    rootStrategyVersionId: str
    currentStrategyVersionId: str
    generation: int
    maxGenerations: int
    recipeId: str | None
    recipeSummary: str | None
    failureProfile: StructuralFailureProfile | None
    proposedDefinition: dict[str, Any] | None
    proposedParameters: dict[str, Any] | None
```

Use `sanitize_selection_metrics()` and `evaluate_selection_gate()` from `bounded_optimizer.py`; hash only the sanitized profile.

- [ ] **Step 4: Implement the deterministic recipe grammar**

Define three versioned recipes using existing `short_cycle_v1` families:

```python
STRUCTURAL_GRAMMAR_VERSION = "structural_strategy_grammar_v1"
MAX_STRUCTURAL_GENERATIONS = 3
RECIPE_ORDER = (
    "regime_confirmed_trend_pullback_v1",
    "volatility_guarded_compression_release_v1",
    "failed_reclaim_rejection_v1",
)
```

Each recipe must preserve timeframe and explicit direction when supported, set `targetR` to the parent value only when it is at least `2.0`, use `two_r_half_atr_runner_v1`, and populate `structuralRedesignLineage` with the approved schema. Recipe selection must be deterministic from profile flags and skip every recipe already present in the lineage.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\evolution\test_structural_redesign.py tests\evolution\test_bounded_optimizer.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit the domain policy**

```powershell
git add alphapilot/evolution/workflow/structural_redesign.py tests/evolution/test_structural_redesign.py
git commit -m "Add bounded structural redesign policy"
```

---

### Task 2: Atomic Redesign Persistence and Idempotent Service

**Files:**
- Modify: `alphapilot/evolution/workflow/repository.py`
- Create: `alphapilot/evolution/workflow/structural_redesign_service.py`
- Test: `tests/evolution/test_structural_redesign_integration.py`

**Interfaces:**
- Consumes: `StructuralRedesignDecision`, terminal `WorkflowRunRecord`, shared SQLite connection, and registry audit records.
- Produces: `process_structural_redesign_result(repository, registry, run) -> StructuralRedesignProcessingResult` and atomic repository methods `commit_structural_redesign` / `commit_structural_redesign_stop`.

- [ ] **Step 1: Write failing atomicity and idempotency tests**

Create a temporary registry, terminal structurally weak backtest, and assert:

```python
first = process_structural_redesign_result(self.workflow, self.registry, failed)
second = process_structural_redesign_result(self.workflow, self.registry, failed)
self.assertEqual(first.childStrategyVersionId, second.childStrategyVersionId)
self.assertEqual(first.childWorkflowRunId, second.childWorkflowRunId)
self.assertEqual(self.workflow.get_strategy_version(parent_id).status, "archived")
self.assertEqual(self.workflow.get_workflow_run(first.childWorkflowRunId).status, "queued")
```

Inject a failure before the final parent update and assert the transaction rolls back: parent remains active, child/run/audits do not exist. Assert a data failure creates no child, and two retries create one child and one event of each type.

- [ ] **Step 2: Run the integration test and verify RED**

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\evolution\test_structural_redesign_integration.py -q
```

Expected: collection fails because the service and repository transaction methods do not exist.

- [ ] **Step 3: Add focused atomic repository commits**

Add methods with exact signatures:

```python
def commit_structural_redesign(
    self,
    *,
    parent_strategy_version_id: str,
    expected_parent_status: str,
    child: StrategyVersionRecord,
    child_run: WorkflowRunRecord,
    child_event: StageEventRecord,
    parent_event: StageEventRecord,
    audit_events: tuple[AuditEventRecord, ...],
) -> None:
    self._commit_structural_records(
        parent_strategy_version_id=parent_strategy_version_id,
        expected_parent_status=expected_parent_status,
        child=child,
        child_run=child_run,
        child_event=child_event,
        parent_event=parent_event,
        audit_events=audit_events,
    )

def commit_structural_redesign_stop(
    self,
    *,
    parent_strategy_version_id: str,
    expected_parent_status: str,
    parent_event: StageEventRecord,
    audit_event: AuditEventRecord,
) -> None:
    self._commit_structural_stop_records(
        parent_strategy_version_id=parent_strategy_version_id,
        expected_parent_status=expected_parent_status,
        parent_event=parent_event,
        audit_event=audit_event,
    )
```

Both methods use one `with self.connection:` block, direct parameterized SQL, existing canonical JSON helpers, and affected-row checks. They must not call repository methods that commit independently.

- [ ] **Step 4: Implement the idempotent service**

Implement:

```python
@dataclass(frozen=True)
class StructuralRedesignProcessingResult:
    action: str
    reasonCode: str
    decisionKey: str | None
    generation: int
    recipeId: str | None
    parentStrategyVersionId: str
    childStrategyVersionId: str | None
    childWorkflowRunId: str | None

def process_structural_redesign_result(
    repository: WorkflowRepository,
    registry: RegistryRepository,
    run: WorkflowRunRecord,
) -> StructuralRedesignProcessingResult:
    return _StructuralRedesignProcessor(repository, registry).process(run)
```

The service must re-read the terminal run, require `strategy_performance`, find the root and used recipes, detect one active structural child, build stable record IDs from the decision key, and write `structural_redesign_candidate_created` plus `structural_redesign_parent_archived` atomically. Stop decisions write `structural_redesign_stopped` and archive a structurally weak terminal parent atomically. Persistence exceptions propagate; no partial state is accepted.

- [ ] **Step 5: Run integration and regression tests**

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\evolution\test_structural_redesign_integration.py tests\evolution\test_bounded_optimization_integration.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit atomic persistence**

```powershell
git add alphapilot/evolution/workflow/repository.py alphapilot/evolution/workflow/structural_redesign_service.py tests/evolution/test_structural_redesign_integration.py
git commit -m "Persist structural redesigns atomically"
```

---

### Task 3: Worker Hook, Recovery Backup, and CLI

**Files:**
- Modify: `alphapilot/evolution/workflow/cli.py`
- Modify: `tests/evolution/test_workflow_cli.py`
- Modify: `tests/evolution/test_structural_redesign_integration.py`

**Interfaces:**
- Consumes: terminal runs after bounded optimization review.
- Produces: automatic queue draining and repeatable `recover-structural-redesigns --strategy-version-id <strategy-version-id>` execution.

- [ ] **Step 1: Write failing worker and recovery tests**

Assert a serial `run-selected-backtests` call processes a structurally weak parent, creates one child, and includes the child run in `drainedWorkflowRunIds`. Assert recovery creates a timestamped `.sqlite` online backup before mutation, is idempotent, and ignores worker/data failures.

- [ ] **Step 2: Run CLI tests and verify RED**

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\evolution\test_workflow_cli.py -k "structural or selected_backtests" -q
```

Expected: tests fail because the CLI command and worker hook are absent.

- [ ] **Step 3: Integrate after bounded optimization**

After `process_bounded_optimization_result(workflow, registry, finished)`, call `process_structural_redesign_result(workflow, registry, finished)`. Preserve the existing pending-queue rescan so the generated child is drained by the same serial worker. Do not change `formalWorkerCount=1` or `dataPrefetchWorkerCount=1`.

- [ ] **Step 4: Add online-backup recovery**

Implement `recover_terminal_structural_redesigns(repository, registry, registry_path, strategy_version_ids=None)` in the service and CLI command:

```powershell
python -m alphapilot.evolution.workflow.cli `
  --registry data/evolution_registry.sqlite `
  recover-structural-redesigns `
  --strategy-version-id <id>
```

The command must use `sqlite3.Connection.backup()` to a sibling `backups/` directory before the first mutation and return `backupPath`, reviewed/created/stopped counts, child run IDs, and decisions.

- [ ] **Step 5: Run CLI and queue-drain tests**

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\evolution\test_workflow_cli.py tests\evolution\test_structural_redesign_integration.py -q
```

Expected: all tests pass and the worker count assertions remain `1`.

- [ ] **Step 6: Commit worker integration**

```powershell
git add alphapilot/evolution/workflow/cli.py alphapilot/evolution/workflow/structural_redesign_service.py tests/evolution/test_workflow_cli.py tests/evolution/test_structural_redesign_integration.py
git commit -m "Run bounded structural redesigns in workflow"
```

---

### Task 4: Projection and Capability-Gated Console Lifecycle

**Files:**
- Modify: `alphapilot/evolution/workflow/projection.py`
- Modify: `tests/evolution/test_structural_redesign_integration.py`
- Modify: `D:/Codex-Workspace/AlphaPilot-Control-Console/alphapilot_control_console/workflow_client.py`
- Modify: `D:/Codex-Workspace/AlphaPilot-Control-Console/web/app.js`
- Modify: `D:/Codex-Workspace/AlphaPilot-Control-Console/tests/test_workflow_client.py`
- Modify: `D:/Codex-Workspace/AlphaPilot-Control-Console/tests/test_workflow_ui_contract.py`

**Interfaces:**
- Consumes: `structuralRedesignLineage` and stable structural audit events.
- Produces: projection object `structuralRedesignCampaign` and Console capability `structuralRedesignRecovery`.

- [ ] **Step 1: Write failing projection and Console contract tests**

Assert the child projection contains:

```python
self.assertEqual(item["structuralRedesignCampaign"]["generation"], 1)
self.assertEqual(item["structuralRedesignCampaign"]["maxGenerations"], 3)
self.assertEqual(item["structuralRedesignCampaign"]["parentStatus"], "archived")
self.assertEqual(item["structuralRedesignCampaign"]["childStatus"], "queued")
self.assertNotIn("holdout", repr(item["structuralRedesignCampaign"]))
```

Console tests assert the capability key and Chinese text `自动重设计 1/3`, `失败父版本已归档`, `生成子策略`, and terminal stop reasons appear only behind the capability flag.

- [ ] **Step 2: Run focused tests and verify RED**

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\evolution\test_structural_redesign_integration.py -q
Set-Location D:\Codex-Workspace\AlphaPilot-Control-Console
& D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m pytest tests\test_workflow_client.py tests\test_workflow_ui_contract.py -q
```

Expected: projection and capability assertions fail.

- [ ] **Step 3: Add structural projection**

Read only `structural_redesign_*` audit events and the child lineage. Return:

```python
"structuralRedesignCampaign": {
    "supported": True,
    "campaignId": lineage.get("campaignId"),
    "generation": int(lineage.get("generation") or 0),
    "maxGenerations": 3,
    "recipeId": lineage.get("recipeId"),
    "recipeSummary": audit_payload.get("recipeSummary"),
    "parentStrategyVersionId": lineage.get("parentStrategyVersionId"),
    "parentStatus": parent.status if parent is not None else None,
    "childStrategyVersionId": child.strategyVersionId if child is not None else None,
    "childWorkflowRunId": child_run.workflowRunId if child_run is not None else None,
    "childStatus": child_run.status if child_run is not None else None,
    "stopReason": audit_payload.get("stopReason"),
    "lastDecisionAt": audit_created_at,
}
```

Return `supported: False` with null lifecycle fields for unrelated versions.

- [ ] **Step 4: Add capability-gated Chinese UI**

Allow `recover-structural-redesigns` in the fixed Console command allowlist, set `structuralRedesignRecovery: true`, and render one compact status strip below existing bounded optimization text. Archived parents remain only under history; active lanes show the child.

- [ ] **Step 5: Run focused tests and JavaScript syntax check**

```powershell
Set-Location D:\Codex-Workspace\AlphaPilot-Quant-Engine
& .\.venv\Scripts\python.exe -m pytest tests\evolution\test_structural_redesign_integration.py -q
Set-Location D:\Codex-Workspace\AlphaPilot-Control-Console
& D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m pytest tests\test_workflow_client.py tests\test_workflow_ui_contract.py -q
node --check web\app.js
```

Expected: all tests pass and Node reports no syntax errors.

- [ ] **Step 6: Commit each repository independently**

Quant Engine:

```powershell
git add alphapilot/evolution/workflow/projection.py tests/evolution/test_structural_redesign_integration.py
git commit -m "Project structural redesign lifecycle"
```

Control Console:

```powershell
git add alphapilot_control_console/workflow_client.py web/app.js tests/test_workflow_client.py tests/test_workflow_ui_contract.py
git commit -m "Show bounded structural redesign lifecycle"
```

---

### Task 5: Documentation, Full Verification, and Safe Recovery Rehearsal

**Files:**
- Modify: `README.md`
- Modify: `D:/Codex-Workspace/AlphaPilot-Control-Console/README.md`

**Interfaces:**
- Consumes: all completed implementation tasks.
- Produces: documented safety model, fully verified repositories, and cloned-registry recovery evidence.

- [ ] **Step 1: Document behavior and hard stops**

Document the three-generation structural budget, separate parameter budget, split-safe evidence, atomic archive/create/queue behavior, recovery backup path, serial worker preservation, Console capability, `targetR >= 2R`, and unchanged Demo/Live gates.

- [ ] **Step 2: Run Quant verification**

```powershell
Set-Location D:\Codex-Workspace\AlphaPilot-Quant-Engine
& .\.venv\Scripts\python.exe -m pytest tests\evolution -q
& .\.venv\Scripts\python.exe -m compileall alphapilot
& .\.venv\Scripts\python.exe -m alphapilot.scripts.validate_config
powershell -ExecutionPolicy Bypass -File scripts\check_safety.ps1
git diff --check
```

Expected: all commands exit `0`; the safety script reports no executable live/withdraw integration introduced by this feature.

- [ ] **Step 3: Run Console verification**

```powershell
Set-Location D:\Codex-Workspace\AlphaPilot-Control-Console
& D:\Codex-Workspace\AlphaPilot-Quant-Engine\.venv\Scripts\python.exe -m pytest -q
node --check web\app.js
git diff --check
```

Expected: all tests pass and syntax/diff checks exit `0`.

- [ ] **Step 4: Rehearse recovery on a cloned registry**

Use Python `sqlite3.Connection.backup()` to copy `data/evolution_registry.sqlite` into `D:\Codex-Workspace\AlphaPilot-Quant-Engine\data\recovery-rehearsal\`, then run `recover-structural-redesigns` against only the clone. Verify `PRAGMA integrity_check` returns `ok`, repeated recovery creates no duplicate child, parent is archived only when child/run/audits exist, and the clone's queued child is visible in projection.

- [ ] **Step 5: Commit documentation**

Quant Engine:

```powershell
git add README.md
git commit -m "Document bounded structural redesign recovery"
```

Control Console:

```powershell
git add README.md
git commit -m "Document structural redesign status display"
```

- [ ] **Step 6: Merge and push only after clean verification**

Use the repository's bundled Git executable to merge each verified worktree branch into `main`, rerun `git status --short --branch`, and push. Do not restart the currently credentialed Console process. Do not apply recovery to the real registry while the existing backtest worker owns an active run; first verify a safe worker boundary, perform an online backup, then run the idempotent recovery command.
