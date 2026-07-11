# Short-Cycle Workflow Candidate Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register ten executable 5m/15m short-cycle candidates, validate them over a historical point-in-time dynamic Top50 universe, preserve the same frozen signal semantics through local forward, and add gated per-card/selected/all controls to Strategy, Local Simulation, and Demo.

**Architecture:** A validated catalog owns the ten configurations. An idempotent workflow bootstrap turns catalog entries into StrategyFamilies and StrategyVersions. Formal backtesting dispatches by `definition.signalEngine`, preserving the existing Alpha191 branch and routing `short_cycle_v1` through a focused signal adapter. A schema-dispatched frozen forward policy reuses the same rules with public completed candles. Quant remains the workflow source of truth; Console batch actions submit only eligible IDs and formal backtests execute in one serial worker.

**Tech Stack:** Python 3.12, pandas, SQLite append-only evolution registry, unittest, PowerShell wrapper, existing AlphaPilot Workflow and Control Console subprocess boundary.

## Global Constraints

- Exactly five 5m and five 15m candidates.
- Fixed `targetR = 2.0`; no lower target is accepted.
- Registration creates only `backtest / awaiting`; it creates no Demo/Live release and no order.
- Formal promotion evidence uses historical point-in-time dynamic Top50; single-symbol runs are smoke/debug only.
- Registration never starts a run. User-triggered selected/all backtests execute serially in one worker.
- Re-running bootstrap is idempotent.
- Existing Alpha191 behavior and current workflow run remain unchanged.
- Existing 8766 Demo process and process-only credentials are not restarted.
- No Trade API, Withdraw API, live permission, or automatic promotion is added.

---

### Task 1: Add the validated short-cycle candidate catalog

**Files:**
- Create: `alphapilot/short_cycle/workflow_candidates.py`
- Create: `tests/short_cycle/test_workflow_candidates.py`

**Interfaces:**
- Produces: `ShortCycleWorkflowCandidate` and `short_cycle_workflow_candidates() -> tuple[ShortCycleWorkflowCandidate, ...]`.
- Consumed by: bootstrap registration and formal signal dispatch tests.

- [ ] **Step 1: Write the failing catalog tests**

```python
def test_catalog_contains_exactly_five_5m_and_five_15m_candidates():
    items = short_cycle_workflow_candidates()
    assert len(items) == 10
    assert Counter(item.timeframe for item in items) == {"5m": 5, "15m": 5}
    assert len({item.family_key for item in items}) == 10

def test_catalog_is_fixed_two_r_and_research_only():
    for item in short_cycle_workflow_candidates():
        definition = item.definition()
        assert definition["targetR"] == 2.0
        assert definition["signalEngine"] == "short_cycle_v1"
        assert definition["researchOnly"] is True
        assert item.parameters["stop_atr"] > 0
        assert item.parameters["max_hold"] > 0
```

- [ ] **Step 2: Run the catalog tests and verify RED**

Run: `python -m unittest tests.short_cycle.test_workflow_candidates -v`

Expected: FAIL because `alphapilot.short_cycle.workflow_candidates` does not exist.

- [ ] **Step 3: Implement the immutable catalog**

```python
@dataclass(frozen=True)
class ShortCycleWorkflowCandidate:
    family_key: str
    display_name: str
    timeframe: str
    direction: str
    signal_family: str
    parameters: dict[str, Any]

    def definition(self) -> dict[str, Any]:
        return {
            "schemaVersion": "short_cycle_strategy_definition_v1",
            "signalEngine": "short_cycle_v1",
            "signalFamily": self.signal_family,
            "market": "crypto_usdt_swap",
            "universePolicy": "point_in_time_dynamic_liquid_usdt_swap",
            "timeframe": self.timeframe,
            "direction": self.direction,
            "targetR": 2.0,
            "researchOnly": True,
            "forwardSignalPolicy": {
                "schemaVersion": "short_cycle_forward_policy_v1",
                "signalEngine": "short_cycle_v1",
                "signalFamily": self.signal_family,
                "timeframe": self.timeframe,
                "direction": self.direction,
                "parameters": self.parameters,
            },
            "backtest": {
                "costModel": {"feeRate": 0.0005, "slippageRate": 0.0005}
            },
        }
```

Populate the exact ten entries from the approved design and validate supported timeframe, direction, family, unique family key, every family-specific required parameter, `stop_atr`, and `max_hold` when the tuple is built. Both `short_breakdown_momentum` entries include `trend_tolerance = 1.0`.

- [ ] **Step 4: Run the catalog tests and verify GREEN**

Run: `python -m unittest tests.short_cycle.test_workflow_candidates -v`

Expected: 2 tests PASS.

### Task 2: Register the pack idempotently in Workflow

**Files:**
- Modify: `alphapilot/evolution/workflow/bootstrap.py`
- Modify: `alphapilot/evolution/workflow/cli.py`
- Modify: `tests/evolution/test_workflow_cli.py`
- Create: `scripts/register_v13_27_3_short_cycle_candidates.ps1`

**Interfaces:**
- Produces: `register_short_cycle_candidate_pack(registry, workflow) -> tuple[StrategyVersionRecord, ...]`.
- Produces CLI command: `bootstrap-short-cycle` returning `{count, strategyVersionIds, displayNames}`.

- [ ] **Step 1: Write failing bootstrap and CLI tests**

```python
def test_short_cycle_bootstrap_is_idempotent_and_awaiting_only(self):
    first = self.run_cli("bootstrap-short-cycle")
    second = self.run_cli("bootstrap-short-cycle")
    projection = self.run_cli("projection")
    assert first == second
    assert first["count"] == 10
    items = [item for item in projection["items"] if item["sourceType"] == "short_cycle_candidate_pack_v13_27_3"]
    assert len(items) == 10
    assert {(item["stage"], item["status"]) for item in items} == {("backtest", "awaiting")}
```

Also query the temporary registry repositories and assert zero `DemoReleases`, zero `LiveReleases`, and no order table writes.

- [ ] **Step 2: Run the targeted CLI test and verify RED**

Run: `python -m unittest tests.evolution.test_workflow_cli.WorkflowCliTests.test_short_cycle_bootstrap_is_idempotent_and_awaiting_only -v`

Expected: FAIL because the command is unavailable.

- [ ] **Step 3: Implement registration and CLI output**

For each catalog entry:

```python
family = ensure_strategy_family(
    repository=registry,
    family_key=item.family_key,
    name=item.display_name,
    metadata={"direction": item.direction, "timeframe": item.timeframe, "candidatePack": "V13.27.3"},
)
version = register_strategy_version(
    workflow,
    strategy_family_id=family.strategyFamilyId,
    display_name=item.display_name,
    source_type="short_cycle_candidate_pack_v13_27_3",
    definition=item.definition(),
    parameters=item.parameters,
    initial_gate_profile_id=gate.gateProfileId,
)
```

Add `bootstrap-short-cycle` to the parser. Return stable ASCII field names and Unicode display values. Keep existing `bootstrap` behavior unchanged.

Create an ASCII-only PowerShell wrapper that enters the Quant root, selects `.venv\Scripts\python.exe`, runs the idempotent command against `data\evolution_registry.sqlite`, and prints the JSON result. It must not start any backtest.

- [ ] **Step 4: Run bootstrap tests and verify GREEN**

Run: `python -m unittest tests.evolution.test_workflow_cli -v`

Expected: all Workflow CLI tests PASS.

### Task 3: Build a short-cycle formal signal adapter

**Files:**
- Create: `alphapilot/evolution/evaluation/short_cycle_signals.py`
- Modify: `alphapilot/short_cycle/parameter_search.py`
- Create: `tests/evolution/test_short_cycle_formal_signals.py`

**Interfaces:**
- Produces: `build_short_cycle_formal_signals(signal_frames, *, signal_timeframe, family, expected_direction, parameters) -> pandas.DataFrame`.
- Output columns: `pair`, `timeframe`, `signalDate`, `signalTimestampMs`, `sourceTimestampMs`, `signalIndex`, `direction`, `setupName`, `stopLossPct`.

- [ ] **Step 1: Write failing signal-adapter tests**

Use deterministic BTC and altcoin frames with 260 completed candles. Patch only the final rows necessary to create one supported-family signal.

```python
signals = build_short_cycle_formal_signals(
    {"BTC-USDT-SWAP": btc, "ETH-USDT-SWAP": eth},
    family="breakout_volume_long",
    parameters=params,
)
assert list(signals["pair"]) == ["ETH/USDT:USDT"]
assert signals.iloc[0]["direction"] == "long"
assert signals.iloc[0]["stopLossPct"] > 0
```

Add tests proving a BTC crash blocks a long signal, an unknown family raises, and output timestamps come only from completed source rows.

- [ ] **Step 2: Run the adapter tests and verify RED**

Run: `python -m unittest tests.evolution.test_short_cycle_formal_signals -v`

Expected: FAIL because the adapter module does not exist.

- [ ] **Step 3: Expose BTC context and implement the adapter**

Rename `_merge_btc_context` to `merge_btc_context` in `parameter_search.py` and update its internal call. Keep `_merge_btc_context = merge_btc_context` as a compatibility alias.

The adapter must:

1. Require BTC from the same signal timeframe and sort each frame by `timestamp_ms`.
2. Apply `add_indicators` and `merge_btc_context`.
3. Call the allowlisted `build_signal` family.
4. Verify the returned direction matches `expected_direction`.
5. Convert each true completed row into the standard signal schema. Canonical timestamps are bar-open timestamps, so set `signalTimestampMs = sourceTimestampMs + signalIntervalMs - 1` while retaining the original `signalIndex` for split membership.
6. Compute `stopLossPct = atr14(signal bar) * stop_atr / close(signal bar)`; reject non-finite or non-positive values.
7. Sort deterministically by signal timestamp and pair.

- [ ] **Step 4: Run signal-adapter and existing parameter-search tests**

Run: `python -m unittest tests.evolution.test_short_cycle_formal_signals -v`

Run: `python -m unittest discover -s tests -p 'test*short_cycle*.py' -v`

Expected: all tests PASS.

### Task 4: Dispatch formal backtesting without changing Alpha191

**Files:**
- Modify: `alphapilot/evolution/evaluation/formal_strategy_backtest.py`
- Modify: `tests/evolution/test_formal_strategy_backtest.py`

**Interfaces:**
- Consumes: `definition.signalEngine`, `definition.signalFamily`, and `build_short_cycle_formal_signals`.
- Preserves: existing Alpha191 observer path when `signalEngine` is absent or `alpha191_observer_v1`.

- [ ] **Step 1: Write failing dispatch tests**

Add one test with a `short_cycle_v1` StrategyVersion and patch `build_short_cycle_formal_signals` to return a deterministic signal containing `stopLossPct`. Assert the formal result uses the signal-specific stop and writes the same manifest-bound evidence.

Add tests that an unknown signal engine raises `formal_signal_engine_not_supported` and the existing Alpha191 test still calls `build_alpha191_observer_signals`.

- [ ] **Step 2: Run formal-backtest tests and verify RED**

Run: `python -m unittest tests.evolution.test_formal_strategy_backtest -v`

Expected: the new short-cycle and unknown-engine tests FAIL while existing tests remain green.

- [ ] **Step 3: Implement explicit dispatch and non-overlap parity**

```python
signal_engine = str(strategy_version.definition.get("signalEngine") or "alpha191_observer_v1")
if signal_engine == "alpha191_observer_v1":
    signals = build_alpha191_observer_signals(panel, overlay_id=overlay_id)
elif signal_engine == "short_cycle_v1":
    signals = build_short_cycle_formal_signals(
        signal_frames,
        family=str(strategy_version.definition.get("signalFamily") or ""),
        parameters=strategy_version.parameters,
    )
else:
    raise ValueError(f"formal_signal_engine_not_supported:{signal_engine}")
```

For short-cycle rows, use `signal.stopLossPct` in each `FixedRPathConfig`. Convert signal-bar holding limits into 5m execution bars (`5m: max_hold`, `15m: max_hold * 3`). Track the last exit timestamp per instrument and skip overlapping short-cycle signals to match the existing short-cycle simulation semantics. Do not apply these rules to Alpha191. Preserve all existing manifest hashes and evidence schema.

- [ ] **Step 4: Run formal and fixed-R tests and verify GREEN**

Run: `python -m unittest tests.evolution.test_formal_strategy_backtest tests.evolution.test_fixed_r_path -v`

Expected: all tests PASS.

### Task 5: Preserve short-cycle semantics in local forward

**Files:**
- Modify: `alphapilot/evolution/workflow/local_forward_bridge.py`
- Modify: `alphapilot/evolution/forward/release.py`
- Modify: `alphapilot/evolution/forward/rules.py`
- Modify: `alphapilot/evolution/forward/runner.py`
- Modify: `tests/evolution/test_local_forward_bridge.py`
- Modify: `tests/evolution/test_forward_rules.py`
- Modify: `tests/evolution/test_forward_runner.py`

**Interfaces:**
- `evaluate_frozen_policy(..., reference_frames: dict[str, pandas.DataFrame] | None = None)` keeps the Alpha191 rules branch and adds `short_cycle_forward_policy_v1`.
- `run_forward_cycle()` loads one same-timeframe BTC reference frame and passes it to each short-cycle evaluation.

- [ ] **Step 1: Write failing short-cycle forward-policy tests**

Create a frozen policy from one catalog entry. Assert that a completed matching bar creates a `ForwardDecision`, its `riskDistance` equals `ATR14 * stop_atr`, a BTC shock blocks the signal, unknown schemas/families fail closed, and existing factor-rule policy tests remain unchanged.

- [ ] **Step 2: Run the policy and bridge tests and verify RED**

Run: `python -m unittest tests.evolution.test_forward_rules tests.evolution.test_forward_runner tests.evolution.test_local_forward_bridge -v`

Expected: short-cycle tests FAIL because only factor-threshold `rules` are accepted.

- [ ] **Step 3: Implement schema-dispatched policy evaluation**

For `short_cycle_forward_policy_v1`, validate `signalEngine`, family, direction, timeframe, parameters, and same-timeframe BTC reference. Use `add_indicators`, `merge_btc_context`, and `build_signal` on completed candles. Evaluate only the final completed row and compute risk distance from that row. Keep the existing factor-rules branch byte-for-byte equivalent in behavior.

Update promotion/release validation to accept either:

```python
bool(policy.get("rules"))
or policy.get("schemaVersion") == "short_cycle_forward_policy_v1"
```

For short-cycle candidate exit metadata, store `stopAtr`, `takeProfitR`, and `maxHoldingBars`; do not require a synthetic fixed `stopLossPct`.

- [ ] **Step 4: Run local-forward tests and verify GREEN**

Run: `python -m unittest tests.evolution.test_forward_rules tests.evolution.test_forward_runner tests.evolution.test_local_forward_bridge -v`

Expected: all tests PASS and no order-creation capability is introduced.

### Task 6: Add controlled serial batch actions

**Files:**
- Modify: `alphapilot/evolution/workflow/cli.py`
- Modify: `tests/evolution/test_workflow_cli.py`
- Modify: `D:/Codex-Workspace/AlphaPilot-Control-Console/alphapilot_control_console/workflow_client.py`
- Modify: `D:/Codex-Workspace/AlphaPilot-Control-Console/alphapilot_control_console/demo_workflow.py`
- Modify: `D:/Codex-Workspace/AlphaPilot-Control-Console/alphapilot_control_console/http_app.py`
- Modify: Console tests covering workflow and Demo actions.

**Interfaces:**
- Quant command: `run-selected-backtests --run-id <id> [--run-id <id> ...]`.
- Console endpoint accepts `{stage, scope, strategyVersionIds}` and returns accepted/rejected IDs plus queue metadata.

- [ ] **Step 1: Write failing eligibility and serialization tests**

Prove selected backtests preserve caller order, reject duplicates/ineligible stages, and invoke one worker loop rather than one child process per strategy. Prove Demo bulk action calls only each card's legal next action and never creates an override.

- [ ] **Step 2: Run targeted tests and verify RED**

Run the new Quant CLI and Console workflow action tests. Expected: FAIL because selected batch commands/endpoints do not exist.

- [ ] **Step 3: Implement the controlled batch boundary**

The Quant selected command resolves current projection records, accepts only `backtest` runs in `awaiting` or `paused`, and runs them sequentially through `_run_dual_layer_once`. Console starts one background batch process and writes a non-secret job log. Demo selected/all iterates immutable eligible releases under existing release/risk checks; it does not bypass or auto-create a release. Local selected/all accepts only eligible local-forward workflow runs and keeps ledgers independent.

- [ ] **Step 4: Run batch-action tests and verify GREEN**

Run all targeted Quant and Console tests. Expected: PASS, with exactly one heavy backtest process per batch.

### Task 7: Add consistent three-page selection controls

**Files:**
- Modify: `D:/Codex-Workspace/AlphaPilot-Control-Console/web/index.html`
- Modify: `D:/Codex-Workspace/AlphaPilot-Control-Console/web/app.js`
- Modify: `D:/Codex-Workspace/AlphaPilot-Control-Console/web/styles.css`
- Modify: Console UI contract tests.

**Interfaces:**
- Per-page selection sets keyed by immutable `strategyVersionId`.
- Actions: per-card start, `启动选中`, and `启动全部待运行`.

- [ ] **Step 1: Write failing DOM/source contract tests**

Assert each of Strategy, Local Simulation, and Demo has a selected-count label and selected/all buttons. Assert eligible cards render a checkbox and ineligible cards render an explicit reason without a selectable checkbox.

- [ ] **Step 2: Run UI contract tests and verify RED**

Expected: FAIL because selected controls do not exist on all three pages.

- [ ] **Step 3: Implement compact accessible controls**

Use native checkboxes, concise Chinese labels, stable control dimensions, and no nested cards. Selection survives refresh only for IDs still eligible. Disable `启动选中` at zero selection. Show accepted/rejected counts after actions. Keep advanced evidence collapsed.

- [ ] **Step 4: Run Node syntax, UI contract, and responsive browser checks**

Verify desktop and 390px widths. Existing navigation and Demo runtime controls remain intact. Do not restart port 8766; static assets may be validated from source or a credential-free alternate test port.

### Task 8: Register the ten candidates and verify the Strategy-page source

**Files:**
- Modify only if tests prove necessary: `D:/Codex-Workspace/AlphaPilot-Control-Console/alphapilot_control_console/workflow_client.py`
- Modify only if tests prove necessary: `D:/Codex-Workspace/AlphaPilot-Control-Console/tests/test_workflow_client.py`
- Runtime data update: `data/evolution_registry.sqlite` through the idempotent CLI only.

**Interfaces:**
- Quant projection is consumed unchanged by `build_workflow_projection()` in Control Console.

- [ ] **Step 1: Add a Console compatibility test only if the command boundary needs it**

If Console must invoke the new command, add `bootstrap-short-cycle` to `ALLOWED_COMMANDS` and test the exact command. Otherwise do not modify Console.

- [ ] **Step 2: Run the production registration wrapper**

Run: `powershell -ExecutionPolicy Bypass -File scripts\register_v13_27_3_short_cycle_candidates.ps1`

Expected: JSON reports exactly ten stable StrategyVersion IDs. It starts no backtest.

- [ ] **Step 3: Verify production projection and safety invariants**

Run the Quant CLI `projection` against `data/evolution_registry.sqlite` and assert:

- all ten approved names exist;
- all ten are `backtest / awaiting`;
- the existing Alpha191 run is unchanged;
- no new DemoRelease or LiveRelease exists;
- no candidate has an order or execution-enabled flag;
- `5m 放量突破延续 ATR1.2` is the documented first manual workflow probe;
- the other nine remain awaiting.

- [ ] **Step 4: Verify the live Control Console API without restarting 8766**

Call `http://127.0.0.1:8766/api/workflow?fresh=1`. Confirm the Strategy-page payload contains the ten new names in the awaiting bucket. Do not restart the process or expose credentials.

### Task 9: Documentation, regression, and release hygiene

**Files:**
- Modify: `README.md`
- Modify: `D:/Codex-Workspace/AlphaPilot-Control-Console/README.md`
- Modify: `docs/superpowers/specs/2026-07-12-short-cycle-workflow-candidate-pack-design.md` only for implementation-result corrections.

- [ ] **Step 1: Document the candidate pack and serial validation rule**

Add a V13.27.3 section listing the ten hypotheses, fixed 2R rule, historical point-in-time dynamic Top50 contract, identical short-cycle semantics across formal/local forward, and three-page selected/all actions. State that registration is not validation and no candidate is yet profitable or live-approved.

- [ ] **Step 2: Run targeted and full Quant verification**

Run:

```powershell
python -m unittest tests.short_cycle.test_workflow_candidates tests.evolution.test_short_cycle_formal_signals tests.evolution.test_workflow_cli tests.evolution.test_formal_strategy_backtest -v
python -m unittest discover -s tests -v
python -m compileall alphapilot
python -m alphapilot.scripts.validate_config
powershell -ExecutionPolicy Bypass -File scripts\check_safety.ps1
git diff --check
```

Expected: all commands PASS; safety scan finds no new executable Trade/Withdraw/live integration.

- [ ] **Step 3: Run Control verification only if Console changed**

Run the targeted Console tests, full test suite, compileall, Node syntax checks, and `git diff --check`. Existing untracked runtime directories remain untouched.

- [ ] **Step 4: Review the final diff and runtime state**

Confirm only intended source/tests/docs/scripts changed; production registry data remains untracked; 8766 still listens on its original process; current Demo runtime remains armed/waiting as before.

- [ ] **Step 5: Commit implementation intentionally**

Commit Quant source/tests/docs without adding `data/`. If Console required no change, do not create a Console commit. Push/tag only after final verification and the existing repository release convention is confirmed.
