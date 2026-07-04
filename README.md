# AlphaPilot Quant Engine

AlphaPilot Quant Engine is the future backend research and execution-control layer for AlphaPilot.

Current version:

```text
AlphaPilot V13.4.12 - Dynamic Universe and Regime Strategy Specification
```

## Positioning

V13.4 prepares real Freqtrade smoke backtest execution and report export on top of the V13.3 strategy implementation.

It is separate from the AlphaPilot Mobile App. The mobile app remains the phone-side AI control panel and manual trade record interface. This repository is the backend quant foundation.

## Safety Boundary

V13.4 does not perform live trading.

- No real Trade API.
- No Withdraw API.
- No real API Key storage.
- No real account reads.
- No real position reads.
- No real order creation.
- No automatic trading.
- No real dry-run execution.
- No public REST API exposure.

All configs are templates for research, backtest preparation, or future dry-run design. Never commit real exchange credentials.

## Why Freqtrade

Freqtrade gives AlphaPilot a practical open-source base for:

- exchange data download
- strategy files
- local backtesting
- dry-run concepts
- structured user_data layout

V13.4 is not a strategy tuning version. It keeps the V13.3 strategy parameters fixed and focuses on the runtime path: data download, Freqtrade backtest, result JSON, and AlphaPilot report export.

## Structure

```text
user_data/                  Freqtrade user data folder
alphapilot/core/            proposal, workflow, lock, handbook skeletons
alphapilot/risk/            risk gate and position sizing skeletons
alphapilot/audit/           JSONL audit ledger skeleton
alphapilot/reports/         report schema and mock export
alphapilot/universe/        fixed Top 30 OKX USDT swap universe
scripts/                    safe PowerShell command wrappers
docs/                       V13.2/V13.3 docs and safety notes
```

## Setup

Install Docker Desktop before running Freqtrade commands.

Check local skeleton status:

```powershell
python -m alphapilot.scripts.print_project_status
python -m alphapilot.scripts.validate_config
```

Compile Python skeleton:

```powershell
python -m compileall alphapilot
```

## Freqtrade Commands

The scripts print commands by default. Use `-Run` only when you intentionally want to execute them.

Download public market data:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1
```

Run a local backtest command template:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_backtest.ps1
```

Export a mock AlphaPilot report:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/export_report.ps1
```

Safety scan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_safety.ps1
```

## V13.3 Volume Rebound V0.1

V13.3 implements the first AlphaPilot research strategy for baseline backtesting:

```text
AlphaPilot Volume Rebound V0.1
```

中文说明：

```text
V13.3 实现第一条 AlphaPilot 自研策略：放量反弹 V0.1。
本版本只用于研究和回测，不进行实盘交易，不接真实 API Key，不创建真实订单。
```

It does not trade live. It does not use real API keys. It is intended for research and backtesting only.

Core V0.1 rules:

- market: OKX USDT swap
- direction: long only
- timeframe: 15m
- fixed universe: Top 30 USDT swap pairs
- fixed stop loss: -3%
- take profit: +3%
- leverage: 5x research cap
- risk per trade: 1% documented research assumption
- fee rate: 0.05% one-way
- slippage rate: 0.05% one-way planned in reports, not yet applied by the Freqtrade command
- BTC crash filter: block new signals when BTC drops at least 1% over the latest three 15m candles
- 4h trend filter: current pair 4h close must be at least `EMA200 * 0.98`

Entry requires RSI14 between 30 and 55, volumeRatio at least 1.5, MACD histogram improvement, price near EMA20, and no chase above the Bollinger middle zone.

Backtest command preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_backtest.ps1 -Smoke -Timerange "20240101-20240701"
```

Download command preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" -Timeframes "15m,1h,4h" -Timerange "20240101-"
```

Add `-Run` only when Docker and Freqtrade are ready.

Report export:

```powershell
python -m alphapilot.reports.export_backtest_report
```

The exporter marks sample reports with `isMock=true`. It marks converted Freqtrade results with `isMock=false`.

The V13.3 strategy is not a live recommendation and not a production trading strategy.

## V13.4 Real Freqtrade Smoke Backtest

V13.4 completed the first real Freqtrade smoke backtest flow:

```text
public historical data download -> Freqtrade backtest -> Freqtrade JSON -> AlphaPilot report
```

The V13.4 smoke run used public OKX historical futures data only:

```text
Pairs: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
Timerange: 20260401-
Trades: 230
Win rate: 41.3043%
Total return: -15.542%
Max drawdown: 24.4939%
Profit factor: 0.8107
```

The versioned report is:

```text
reports/v13_4_smoke_backtest_report.json
```

It is a real converted Freqtrade result and contains:

```json
{
  "isMock": false
}
```

Runtime compatibility fixed in V13.4:

- `scripts/download_data.ps1` supports `-UseTop30`.
- `scripts/run_backtest.ps1` supports `-UseTop30`.
- Freqtrade 2026.6 config requires `entry_pricing` and `exit_pricing`; both are present in the backtest config and dry-run template.
- The report exporter supports the newer Freqtrade result layout where `.last_result.json` points to a zip file containing the real result JSON.
- Report export preserves missing real metrics as `null` and records `reportWarnings`.
- Real dynamic reports write `reports/latest_backtest_report.json` and `reports/smoke_backtest_report.json`; these are ignored so reruns do not pollute git status.
- Mock reports remain explicitly marked with `isMock=true`.

V13.4 is a process success, not a strategy approval. The current AlphaPilot Volume Rebound V0.1 smoke result is negative, with `profitFactor < 1`, negative total return, and high drawdown. It must not enter Dry-run. The next step is V13.4.1 Backtest Result Diagnosis.

## V13.4.1 Backtest Result Diagnosis

V13.4.1 diagnoses the first real smoke backtest result. It does not tune
strategy parameters, does not modify `AlphaPilotVolumeReboundV01.py`, and does
not enter Dry-run.

Run diagnosis:

```powershell
python -m alphapilot.reports.diagnose_backtest_result
```

Diagnosis outputs:

```text
reports/v13_4_1_diagnosis_report.json
reports/v13_4_1_diagnosis_summary.md
docs/V13.4.1-backtest-result-diagnosis.md
docs/v13_4_1_diagnosis_findings.md
```

Main findings from V13.4.1:

- The strategy cannot enter Dry-run.
- SOL contributed the largest pair-level loss: `-94.83085485 USDT`.
- April 2026 contributed the largest time-period loss: `-158.49408035 USDT`.
- `stop_loss` was the largest exit-reason loss: `-420.36251129 USDT`.
- `macd_histogram_two_candle_weakness` also lost heavily: `-345.28583144 USDT`.
- The weakest holding bucket was `1-3h`: `-120.76496941 USDT`.
- Fees were applied by Freqtrade and are material; slippage was not applied by the V13.4 command.
- Filter effectiveness is unavailable because V13.4 did not include skipped-signal instrumentation.

V13.4.1 prepares V0.2 candidate ideas, but those ideas are evidence categories,
not parameter changes. The next work should add signal audit instrumentation and
review the V0.2 candidates before any strategy modification.

## V13.4.2 Signal Audit Instrumentation

V13.4.2 adds skipped-signal audit instrumentation and filter effectiveness
tracking for AlphaPilot Volume Rebound V0.1.

This version does not tune strategy parameters, does not enter Dry-run, does not
call exchange private APIs, and does not create orders.

Run the audit:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_signal_audit.ps1
```

Outputs:

```text
reports/v13_4_2_signal_audit_report.json
reports/v13_4_2_signal_audit_summary.md
docs/V13.4.2-signal-audit-instrumentation.md
docs/filter-effectiveness-methodology.md
```

Current V13.4.2 smoke audit:

```text
Candles evaluated: 26496
Base candidate count: 26496
Final entry count: 305
Actual trade count: 230
Filter effectiveness available: true
Top skip reason: weak_4h_trend
Data missing count: 0
```

The largest primary blocks in the smoke sample are 4h trend, RSI, and volume
ratio. The least primary-blocking filter is the no-chase filter. These findings
prepare V13.4.3 strategy V0.2 candidate design, but V13.4.2 does not change the
V0.1 thresholds.

## V13.4.3 Strategy V0.2 Candidate Design

V13.4.3 creates evidence-based V0.2 strategy candidates from the V13.4.1
diagnosis and V13.4.2 signal audit. It does not tune parameters, does not run
Dry-run, does not change the V0.1 strategy, and prepares V13.4.4 comparative
backtesting.

V13.4.3 基于 V13.4.1 亏损诊断和 V13.4.2 信号审计，提出 V0.2 候选修改方向。本版本不调参、不进入
Dry-run、不修改 V0.1 真实策略，只为 V13.4.4 对比回测做准备。

Run candidate matrix generation:

```powershell
python -m alphapilot.reports.generate_v02_candidate_matrix
```

Outputs:

```text
reports/v13_4_3_v02_candidate_matrix.json
reports/v13_4_3_v02_candidate_summary.md
docs/V13.4.3-strategy-v02-candidate-design.md
docs/volume-rebound-v02-candidate-plan.md
```

V13.4.3 candidates:

```text
V0.2A Trend Strict Filter
V0.2B Volume Quality Filter
V0.2C Exit Cleanup
V0.2D Early Failure Exit
V0.2E Pair Risk Watchlist
```

All candidates are `candidate_only`. None are approved for Dry-run or live
trading.

## V13.4.4 V0.1 vs V0.2 Comparative Backtest

V13.4.4 compares V0.1 baseline with V0.2 candidate strategies using the same
smoke backtest scope. It does not enter Dry-run. It does not approve live
trading. It only identifies candidates for further validation.

V13.4.4 在同一 smoke 回测范围内比较 V0.1 baseline 与 V0.2 候选策略。本版本不进入 Dry-run，不批准实盘，只筛选值得进一步验证的候选。

Run comparative backtest:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_comparative_backtest.ps1 -Timerange "20260401-" -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" -Run
python -m alphapilot.reports.generate_comparative_backtest_report
```

Outputs:

```text
reports/v13_4_4_comparative_manifest.json
reports/v13_4_4_comparative_backtest_report.json
reports/v13_4_4_comparative_backtest_summary.md
docs/V13.4.4-comparative-backtest.md
docs/volume-rebound-v02-comparison-results.md
```

Result summary:

```text
V0.1 baseline: -15.542% return, 24.4939% drawdown, 0.8107 profit factor
V0.2A Trend Strict: -11.6607% return, 21.0664% drawdown, 0.8251 profit factor
V0.2B Volume Quality: -4.0845% return, 11.4841% drawdown, 0.9104 profit factor
V0.2C Exit Cleanup: -6.1609% return, 17.8594% drawdown, 0.9319 profit factor
V0.2D Early Failure Exit: -15.6258% return, 24.3002% drawdown, 0.7979 profit factor
V0.2E Pair Risk Watchlist: -10.3361% return, 17.93% drawdown, 0.8406 profit factor
```

A/B/C/E improved against the baseline comparison gate, while D did not. All
candidate returns are still negative, so `dryRunApproved=false`.

Smoke preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" -Timeframes "15m,1h,4h" -Timerange "20260401-"
powershell -ExecutionPolicy Bypass -File scripts/run_backtest.ps1 -Timerange "20260401-" -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT"
```

Add `-Run` only after Docker Desktop is installed and running.

## V13.4.5 Expanded Candidate Validation

V13.4.5 expands validation of the best V0.2 candidates on a larger Top30 scope
and adds slippage-adjusted metrics.

V13.4.5 对 V13.4.4 中相对较好的 B/C/E 候选进行 Top30 扩大验证，并加入滑点调整后的指标。
本版本不进入 Dry-run，不批准实盘。

Run expanded validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -UseTop30 -Timeframes "15m,1h,4h" -Timerange "20260101-" -Prepend -Run
powershell -ExecutionPolicy Bypass -File scripts/run_expanded_validation.ps1 -UseTop30 -Timerange "20260101-" -Run
python -m alphapilot.reports.generate_expanded_validation_report
```

Outputs:

```text
reports/v13_4_5_expanded_validation_manifest.json
reports/v13_4_5_expanded_validation_report.json
reports/v13_4_5_expanded_validation_summary.md
docs/V13.4.5-expanded-validation-slippage.md
docs/volume-rebound-expanded-validation-results.md
```

V13.4.5 result:

```text
Requested pairs: fixed Top30
Supported pairs: 28
Excluded pairs: TON/USDT:USDT, FET/USDT:USDT
Best raw candidate: AlphaPilotVolumeReboundV02CExitCleanup
Best slippage-adjusted candidate: AlphaPilotVolumeReboundV02CExitCleanup
dryRunApproved: false
```

All candidates remain negative after slippage post-processing. V02C is the best
relative candidate by profit factor, but it is not approved for Dry-run. The
next step should be V13.4.6 strategy direction review or V03 redesign.

## V13.4.6 Strategy Direction Review

V13.4.6 formally closes the current Volume Rebound V0.1/V0.2 research series
for Dry-run consideration and starts the V03 redesign stage.

中文说明：

```text
V13.4.6 基于 V13.4.5 扩大验证和滑点调整结果，正式复盘 Volume Rebound V0.1/V0.2 当前系列失败原因，并提出 V03 重设方向。
本版本不调参、不回测、不进入 Dry-run、不实盘。
```

Run the direction review:

```powershell
python -m alphapilot.reports.generate_strategy_direction_review
```

Outputs:

```text
reports/v13_4_6_strategy_direction_review.json
reports/v13_4_6_strategy_direction_summary.md
reports/v13_4_6_strategy_status_archive.json
docs/V13.4.6-strategy-direction-review.md
docs/volume-rebound-failure-review.md
docs/volume-rebound-v03-redesign-plan.md
```

V13.4.6 decision:

```text
strategyFamilyStatus = rejected_for_dry_run
dryRunApproved = false
```

Main conclusion:

- V0.1/V0.2 should not enter Dry-run.
- B/C/E are relative improvements only; expanded validation and slippage still reject them.
- The failure is not a single-parameter issue.
- V03 should redesign entry quality, trade frequency, reward/risk, trend structure, pair exposure, cost sensitivity, market regime, and signal confirmation.

V03 candidate directions:

- V03A Trend Pullback Continuation
- V03B Breakout Retest Confirmation
- V03C High Score Signal Only
- V03D 1h Main Timeframe

V03 quality gate before any Dry-run discussion:

- slippage-adjusted total return > 0
- slippage-adjusted profit factor > 1.15
- max drawdown materially below V0.1/V0.2 expanded validation
- no single pair dominates profit or loss
- smoke plus six-month Top30 validation must pass

V13.4.6 is research-only. It does not modify V0.1/V0.2 strategy code, does not
run backtests, does not enter Dry-run, does not use API keys, does not call
Trade API or Withdraw API, does not read accounts, does not create orders, and
does not auto trade.

## V13.4.7 V03 Candidate Selection

V13.4.7 selects Trend Pullback 1H as the first V03 implementation direction.
It does not implement strategy code, does not run backtests, and does not enter
Dry-run.

中文说明：

```text
V13.4.7 基于 V13.4.6 策略方向复盘，选择“1h 趋势回调延续”作为 V03 第一实现方向。
本版本只输出策略规格和 V13.4.8 实现计划，不写策略代码、不回测、不进入 Dry-run。
```

Selected V03 direction:

```text
selectedDirection = V03A+D
selectedStrategyId = alpha_trend_pullback_1h_v01
selectedStrategyName = AlphaPilot Trend Pullback 1H V0.1
status = spec_only
dryRunApproved = false
implementedStrategyCode = false
backtestExecuted = false
```

Outputs:

```text
alphapilot/strategy_specs/trend_pullback_1h_v01.py
alphapilot/reports/generate_v03_selection_report.py
reports/v13_4_7_v03_selection_report.json
reports/v13_4_7_v03_strategy_spec.md
docs/V13.4.7-v03-candidate-selection.md
docs/trend-pullback-1h-v01-spec.md
docs/v13_4_8_implementation_plan.md
```

V13.4.7 is research-only. It does not modify strategy execution files, does not
download data, does not run backtests, does not enter Dry-run, does not use API
keys, does not call Trade API or Withdraw API, does not read accounts, does not
create orders, and does not auto trade.

## V13.4.8 Trend Pullback 1H Smoke Backtest

V13.4.8 implements the V13.4.7 selected V03A+D direction as a real Freqtrade
strategy and runs a BTC/ETH/SOL smoke backtest.

中文说明：

```text
V13.4.8 实现 AlphaPilot Trend Pullback 1H V0.1，并完成 BTC / ETH / SOL 真实 Freqtrade 冒烟回测。
本版本仍然不进入 Dry-run，不实盘，不接 API Key，不自动交易。
```

Strategy:

```text
strategyClass = AlphaPilotTrendPullback1HV01
strategyId = alpha_trend_pullback_1h_v01
strategyName = AlphaPilot Trend Pullback 1H V0.1
timeframe = 1h
can_short = false
stoploss = -2.5%
minimal_roi = +5%
dryRunApproved = false
```

Smoke result:

```text
pairs = BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
timerange = 20260401-
isMock = false
tradeCount = 61
totalReturnPct = 6.6227
maxDrawdownPct = 9.8727
winRate = 47.541
profitFactor = 1.1933
```

Outputs:

```text
user_data/strategies/AlphaPilotTrendPullback1HV01.py
reports/v13_4_8_trend_pullback_1h_smoke_report.json
reports/v13_4_8_trend_pullback_1h_smoke_summary.md
docs/V13.4.8-trend-pullback-1h-smoke-backtest.md
docs/trend-pullback-1h-v01-implementation.md
```

V13.4.8 smoke success does not approve Dry-run. It is a research checkpoint only.

## V13.4.9 Trend Pullback Expanded Validation

V13.4.9 expands the V13.4.8 Trend Pullback 1H smoke result to a fixed Top30
validation scope and applies AlphaPilot slippage post-processing.

中文说明：

```text
V13.4.9 将 V13.4.8 的 BTC / ETH / SOL 冒烟结果扩大到固定 Top30 样本，并加入滑点后处理。
扩大验证失败，仍然不进入 Dry-run，不实盘，不接 API Key，不自动交易。
```

Run expanded validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 -UseTop30 -Timeframes "1h,4h" -Timerange "20260101-" -Prepend -Run
powershell -ExecutionPolicy Bypass -File scripts/run_trend_pullback_expanded_validation.ps1 -UseTop30 -Timerange "20260101-" -Run
python -m alphapilot.reports.generate_trend_pullback_expanded_report
```

Result:

```text
requestedPairCount = 30
supportedPairs = 28
excludedPairs = TON/USDT:USDT, FET/USDT:USDT
isMock = false
dryRunApproved = false

rawTradeCount = 472
rawTotalReturnPct = -61.0503
rawMaxDrawdownPct = 67.296
rawWinRate = 31.5678
rawProfitFactor = 0.7067
rawMaxConsecutiveLosses = 13

slippageAdjustedTotalReturnPct = -113.218
slippageAdjustedProfitFactor = 0.5361
slippageAdjustedWinRate = 30.7203
slippageAdjustedMaxDrawdownPct = 112.2244
slippageCost = 521.67704423
```

Outputs:

```text
reports/v13_4_9_trend_pullback_expanded_manifest.json
reports/v13_4_9_trend_pullback_expanded_validation_report.json
reports/v13_4_9_trend_pullback_expanded_validation_summary.md
docs/V13.4.9-trend-pullback-expanded-validation.md
docs/trend-pullback-1h-expanded-results.md
```

V13.4.9 rejects Dry-run. The V13.4.8 smoke result did not generalize to the
wider Top30 validation sample. The next step should be V13.4.10 Trend Pullback
Redesign Review.

## V13.4.10 Trend Pullback Redesign Review

V13.4.10 reads the V13.4.8 smoke report and V13.4.9 expanded validation report
to explain why the small-sample Trend Pullback result failed to generalize.

中文说明：

```text
V13.4.10 只做失败复盘和重设评审。
本版本不调参、不修改策略代码、不下载数据、不运行回测、不进入 Dry-run、不实盘。
```

Run the review:

```powershell
python -m alphapilot.reports.generate_trend_pullback_redesign_review
```

Decision:

```text
strategyId = alpha_trend_pullback_1h_v01
currentStatus = needs_redesign
dryRunApproved = false
recommendedNextStep = V13.4.11 - Execution Reality and Liquidity Gate Design
```

Key conclusion:

```text
V13.4.8 BTC/ETH/SOL smoke:
tradeCount = 61
totalReturnPct = 6.6227
profitFactor = 1.1933
maxDrawdownPct = 9.8727

V13.4.9 Top30 raw:
tradeCount = 472
totalReturnPct = -61.0503
profitFactor = 0.7067
maxDrawdownPct = 67.296

V13.4.9 slippage-adjusted:
totalReturnPct = -113.218
profitFactor = 0.5361
maxDrawdownPct = 112.2244
```

Outputs:

```text
reports/v13_4_10_trend_pullback_redesign_review.json
reports/v13_4_10_trend_pullback_redesign_summary.md
docs/V13.4.10-trend-pullback-redesign-review.md
docs/trend-pullback-expanded-failure-analysis.md
docs/v13_4_11_next-step-options.md
```

V13.4.10 recommends redesigning the research gate around execution reality,
liquidity, market regime, pair universe, and signal quality before another
strategy implementation.

## V13.4.11 Execution Reality and Liquidity Gate Design

V13.4.11 adds the execution reality design layer required before any future
Dry-run candidate review. It does not tune strategy parameters, does not run a
backtest, does not enter Dry-run, and does not create real orders.

中文说明：

```text
V13.4.11 补上执行真实性测试层和流动性闸门。
本版本只做设计骨架和报告，不调参、不回测、不进入 Dry-run、不实盘。
```

Implemented modules:

```text
alphapilot/execution_reality/liquidity_gate.py
alphapilot/execution_reality/slippage_model.py
alphapilot/execution_reality/order_impact.py
alphapilot/execution_reality/shadow_trading_schema.py
alphapilot/execution_reality/live_feasibility_score.py
```

Generate the design report:

```powershell
python -m alphapilot.reports.generate_execution_reality_design_report
```

Outputs:

```text
reports/v13_4_11_execution_reality_design_report.json
reports/v13_4_11_execution_reality_summary.md
docs/V13.4.11-execution-reality-liquidity-gate.md
docs/liquidity-gate-design.md
docs/shadow-trading-design.md
docs/live-feasibility-score.md
```

V13.4.11 updates the proposal schema with optional execution reality context
fields and updates the risk gate so Dry-run candidate review requires liquidity,
execution reality, and shadow trading evidence first.

Safety boundary:

- No real API key.
- No Trade API.
- No Withdraw API.
- No real account reads.
- No real position reads.
- No real order creation.
- No automatic trading.
- No Dry-run execution.

V13.4.11 keeps `dryRunApproved=false` and `liveTradingApproved=false`.

## V13.4.12 Dynamic Universe and Regime Strategy Specification

V13.4.12 defines the new AlphaPilot strategy mainline:

```text
AlphaPilot Dynamic Regime Strategy V0.1
```

中文说明：

```text
V13.4.12 正式切换到动态币种池 + 市场状态路由 + 概率评分的新策略主线。
本版本只做规格，不写策略代码、不下载数据、不回测、不进入 Dry-run、不实盘。
```

New architecture:

```text
Universe -> Regime -> Module -> Probability -> Liquidity -> Risk -> Backtest / Shadow
```

V13.4.12 defines:

- `DynamicUniverseV01`
- historical dynamic universe snapshots
- `MarketRegimeRouterV01`
- `TrendContinuationModuleV01`
- `MeanReversionModuleV01`
- `ProbabilityScoreV01`
- liquidity gate integration
- risk gate integration
- the backtest validation plan

Generate the specification report:

```powershell
python -m alphapilot.reports.generate_dynamic_regime_strategy_spec
```

Outputs:

```text
reports/v13_4_12_dynamic_regime_strategy_spec.json
reports/v13_4_12_dynamic_regime_strategy_summary.md
docs/V13.4.12-dynamic-universe-regime-strategy-specification.md
docs/dynamic-universe-design.md
docs/market-regime-router-design.md
docs/probability-score-design.md
```

V13.4.12 keeps `dryRunApproved=false` and `liveTradingApproved=false`. The next
recommended step is V13.4.13 Historical Dynamic Universe Builder.

## Next Versions

- V13.4.13: build historical Dynamic Universe snapshots without lookahead bias.
- V13.4.14: build Probability Score dataset and label tables.
- V13.4.15: implement Dynamic Regime Strategy V0.1.
- V13.4.16: run Dynamic Regime smoke backtest.
- V13.4.17: run expanded validation with slippage and liquidity gates.
- V13.5: add Shadow Trading Skeleton after the dynamic strategy research layer.
- V13.6: consider Dry-run candidate evaluation only after stronger validation.
