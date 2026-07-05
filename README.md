# AlphaPilot Quant Engine

AlphaPilot Quant Engine is the future backend research and execution-control layer for AlphaPilot.

Current version:

```text
AlphaPilot V13.5.8 - Adaptive ML Factor Discovery
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

## V13.4.13 Historical Dynamic Universe Builder

V13.4.13 implements the historical Dynamic Universe builder needed by the new
Dynamic Regime strategy mainline.

中文说明：

```text
V13.4.13 基于本地公开历史 OHLCV，为每个历史日期生成当时可见的动态币种池快照。
本版本不写策略代码、不下载数据、不运行回测、不进入 Dry-run、不实盘。
```

Run the builder:

```powershell
python -m alphapilot.universe.build_historical_dynamic_universe
```

or:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_dynamic_universe.ps1 -Timerange "20260101-" -RefreshFrequency "daily" -MaxPairs 10
```

Outputs:

```text
reports/v13_4_13_dynamic_universe_snapshots.json
reports/v13_4_13_dynamic_universe_sample_snapshots.json
reports/v13_4_13_dynamic_universe_build_report.json
reports/v13_4_13_dynamic_universe_summary.md
docs/V13.4.13-historical-dynamic-universe-builder.md
docs/historical-dynamic-universe-builder.md
docs/dynamic-universe-lookahead-bias-protection.md
```

Lookahead bias rule:

```text
Each snapshot uses only candles with date < snapshotDate 00:00 UTC.
```

V13.4.13 reads local public OHLCV files only. It does not run a strategy
backtest, enter Dry-run, use API keys, call Trade API or Withdraw API, read
accounts, read positions, create orders, or auto trade.

## V13.4.14 Probability Score Dataset and Label Builder

V13.4.14 builds the statistical probability layer needed by the Dynamic Regime
strategy mainline. It reads V13.4.13 historical universe snapshots and local
public OHLCV, then creates point-in-time candidate samples, forward TP/SL
labels, MFE/MAE metrics, and a probability score table.

中文说明：

```text
V13.4.14 基于历史动态币种池和本地公开 OHLCV，构建概率评分样本、未来标签和条件概率表。
本版本只做统计数据集和标签，不写策略代码、不运行回测、不进入 Dry-run、不实盘。
```

Run the builder:

```powershell
python -m alphapilot.probability.build_probability_dataset
```

or:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_probability_dataset.ps1
```

Outputs:

```text
reports/v13_4_14_probability_dataset_report.json
reports/v13_4_14_probability_score_table.json
reports/v13_4_14_probability_sample_dataset.json
reports/v13_4_14_probability_dataset_summary.md
docs/V13.4.14-probability-score-dataset-label-builder.md
docs/probability-score-methodology.md
docs/probability-label-definition.md
```

No-lookahead rule:

```text
Features are point-in-time. Forward labels are evaluation-only and never flow back into feature buckets.
```

V13.4.14 produced 1,540 labeled samples across 155 historical snapshots. Most
bucket combinations are marked `insufficient_sample`, which keeps the decision
policy conservative and `observe_only`. V13.4.14 does not run a backtest, enter
Dry-run, use API keys, call Trade API or Withdraw API, read accounts, read
positions, create orders, or auto trade.

## V13.4.15 Dynamic Regime Strategy V0.1 Implementation

V13.4.15 implements the first Freqtrade strategy file for the Dynamic Regime
mainline:

```text
user_data/strategies/AlphaPilotDynamicRegimeV01.py
```

中文说明：

```text
V13.4.15 实现 AlphaPilot Dynamic Regime Strategy V0.1 的第一版策略代码。
本版本只写策略代码和文档，不运行回测、不进入 Dry-run、不实盘。
```

The strategy includes:

- Dynamic Universe filter from `reports/v13_4_13_dynamic_universe_snapshots.json`.
- Market Regime Router with `trend`, `mean_reversion`, and `avoid`.
- TrendContinuationModuleV01.
- MeanReversionModuleV01.
- ProbabilityScoreV01 lookup from `reports/v13_4_14_probability_score_table.json`.
- LiquidityGateV01 audit fallback for backtest research only.
- Audit columns prefixed with `ap_dyn_audit_`.

Static validation:

```powershell
python -m py_compile user_data\strategies\AlphaPilotDynamicRegimeV01.py
python -m compileall alphapilot
python -m alphapilot.scripts.validate_config
powershell -ExecutionPolicy Bypass -File scripts\check_safety.ps1
```

V13.4.15 does not run Freqtrade backtests, enter Dry-run, use API keys, call
Trade API or Withdraw API, read accounts, read positions, create orders, or
auto trade.

## V13.4.16 Dynamic Regime Strategy Smoke Backtest

V13.4.16 runs the first real smoke backtest for `AlphaPilotDynamicRegimeV01`.
It validates that Docker/Freqtrade can load the strategy, read the dynamic
universe and probability score table, and produce a real Freqtrade result.

中文说明：

```text
V13.4.16 对 AlphaPilotDynamicRegimeV01 执行 BTC / ETH / SOL 的真实本地 smoke backtest。
本版本不进入 Dry-run，不实盘，不接真实 API Key，不自动交易。
```

Run commands:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_data.ps1 -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" -Timeframes "1h,4h" -Timerange "20260401-" -Run
powershell -ExecutionPolicy Bypass -File scripts\run_dynamic_regime_smoke_backtest.ps1 -Pairs "BTC/USDT:USDT,ETH/USDT:USDT,SOL/USDT:USDT" -Timerange "20260401-" -Timeframe "1h" -Run
python -m alphapilot.reports.generate_dynamic_regime_smoke_report
```

Outputs:

```text
reports/v13_4_16_dynamic_regime_smoke_report.json
reports/v13_4_16_dynamic_regime_smoke_summary.md
docs/V13.4.16-dynamic-regime-smoke-backtest.md
```

Smoke result:

```text
isMock: false
tradeCount: 0
totalReturnPct: 0.0
maxDrawdownPct: 0.0
probabilityScorePass: 0
finalEntrySignals: 0
```

The zero-trade result is expected from the current strict probability score
gate: V13.4.14 produced no `research_candidate` buckets for the smoke context.
The strategy runtime path is valid, but the probability gate blocks entries.
V13.4.16 keeps `dryRunApproved=false` and `liveTradingApproved=false`.

## V13.4.17 Dynamic Regime Expanded Validation

V13.4.17 expands `AlphaPilotDynamicRegimeV01` validation from the BTC / ETH /
SOL smoke scope to the historical dynamic universe.

Scope:

```text
strategy: AlphaPilotDynamicRegimeV01
timeframe: 1h
timerange: 20260101-
universe: historical dynamic universe selectedPairs union
slippage stress: 0.05%, 0.10%, 0.20%, 0.30% one-way
```

Run expanded validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_dynamic_regime_expanded_validation.ps1 -Timerange "20260101-" -Run
python -m alphapilot.reports.generate_dynamic_regime_expanded_report
```

Outputs:

```text
reports/v13_4_17_dynamic_regime_expanded_report.json
reports/v13_4_17_dynamic_regime_expanded_summary.md
docs/V13.4.17-dynamic-regime-expanded-validation.md
```

V13.4.17 reports raw metrics, slippage-adjusted metrics, liquidity gate
summary, probability score summary, probability bucket performance, and
regime/module breakdown. It keeps `dryRunApproved=false` and
`liveTradingApproved=false` regardless of research gate outcome.

Expanded validation result:

```text
isMock: false
pairCount: 27
tradeCount: 0
probabilityScorePass: 0
finalEntrySignals: 0
qualityGatePassed: false
```

Interpretation: the expanded runtime path works, but the V13.4.14 probability
gate still blocks all entries. This is not a strategy approval and not a
Dry-run candidate.

## V13.4.18 Dynamic Regime Pipeline Diagnosis

V13.4.18 diagnoses the zero-trade V13.4.17 result without running a new
backtest and without changing strategy rules, probability thresholds, bucket
tables, regime router logic, module rules, liquidity logic, Dry-run settings,
API keys, account access, order creation, or auto-trading behavior.

Run diagnosis:

```powershell
python -m alphapilot.reports.generate_dynamic_regime_signal_pipeline_diagnosis
```

Outputs:

```text
reports/v13_4_18_dynamic_regime_pipeline_diagnosis_report.json
reports/v13_4_18_dynamic_regime_pipeline_diagnosis_summary.md
docs/V13.4.18-dynamic-regime-pipeline-diagnosis.md
docs/probability-gate-coverage-diagnosis.md
docs/bucket-key-consistency-check.md
```

Diagnosis result:

```text
rowsEvaluated: 119679
trendModuleCandidates: 598
meanReversionModuleCandidates: 1775
probabilityLookupHits: 62352
probabilityScorePass: 0
finalEntrySignals: 0
researchCandidateBuckets: 0
currentGatePassBuckets: 0
bucketKeyMismatchSuspected: false
```

Interpretation: the signal pipeline reaches module candidate generation, but
the probability layer has no current-gate pass buckets. Bucket key format
appears consistent, so the likely V13.4.19 direction is probability bucket
coarsening and sample coverage expansion, not strategy approval.

## V13.4.19 Probability Bucket Coarsening

V13.4.19 reads the existing V13.4.14 probability score table and V13.4.18
pipeline diagnosis, then generates research-only coarsened bucket tables. It
does not modify `AlphaPilotDynamicRegimeV01.py`, does not modify the original
probability score table, does not loosen the current gate, does not run a
backtest, does not enter Dry-run, and does not approve live trading.

Run coarsening analysis:

```powershell
python -m alphapilot.reports.generate_probability_bucket_coarsening_report
```

Outputs:

```text
reports/v13_4_19_probability_bucket_coarsening_report.json
reports/v13_4_19_probability_bucket_coarsening_summary.md
reports/v13_4_19_probability_score_table_coarse_a.json
reports/v13_4_19_probability_score_table_coarse_b.json
reports/v13_4_19_probability_score_table_coarse_c.json
reports/v13_4_19_probability_score_table_coarse_d.json
docs/V13.4.19-probability-bucket-coarsening.md
docs/probability-bucket-coverage-expansion.md
docs/probability-gate-research-vs-trading.md
```

Result summary:

```text
original currentGatePassBucketCount: 0
original researchGatePassBucketCount: 0
original exploratoryGatePassBucketCount: 2
coarse_a researchGatePassBucketCount: 0
coarse_b researchGatePassBucketCount: 0
coarse_c researchGatePassBucketCount: 2
coarse_d researchGatePassBucketCount: 2
rootCauseConclusion: A. probability_table_too_sparse
recommendedNextStep: V13.4.20 - Probability Gate Candidate Wiring and Backtest Plan
```

Important limitation: the full raw probability sample dataset is not committed,
so V13.4.19 aggregates the existing bucket-level score table. Profit factor in
the coarsened tables is a sample-count weighted bucket-level approximation, not
a raw win/loss recomputation.

The current gate still has zero pass buckets after coarsening. Coarse C/D only
create research buckets, so they are candidates for a future backtest plan, not
Dry-run or live-trading approval.

## V13.4.20 Alpha Factor Research Layer

V13.4.20 changes the next step after V13.4.19. Instead of wiring coarse
probability buckets into strategy entry logic, it designs AlphaPilot's own Alpha
Factor Research Layer and Benchmark Strategy Suite.

中文说明：V13.4.20 基于 alpha101 的因子研究思路和 CryptoAgentPro.beta 的策略 / 市场状态参考，设计 AlphaPilot 自己的因子研究层和基准策略组。本版本不写交易策略、不回测、不进入 Dry-run、不接真实 API Key。

Why this route changed:

```text
V13.4.19 found coarse C / D research buckets, but the full raw sample dataset
is not committed and coarse profit factor is a bucket-level approximation.
Those buckets should not be promoted directly into strategy entries.
```

Generate the design report:

```powershell
python -m alphapilot.reports.generate_alpha_factor_research_design
```

Outputs:

```text
reports/v13_4_20_alpha_factor_research_design.json
reports/v13_4_20_alpha_factor_research_summary.md
docs/V13.4.20-alpha-factor-research-layer.md
docs/factor-data-panel-design.md
docs/factor-operator-subset.md
docs/benchmark-strategy-suite.md
docs/strategy-research-factory.md
```

The design includes:

```text
FactorDataPanel schema
Factor operator subset
Manual Factor Library V01
Factor Evaluation Metrics
Benchmark Strategy Suite
Strategy Research Factory
Dynamic Universe / Regime Router integration boundary
```

V13.4.20 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no strategy implementation
no backtest execution
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.21 FactorDataPanel and Manual Factor Library

V13.4.21 implements the local research data layer designed in V13.4.20. It
reads local public Freqtrade OHLCV files, builds a point-in-time
FactorDataPanel sample, and computes the first Manual Factor Library V01.

Run the builder:

```powershell
python -m alphapilot.factors.build_factor_data_panel
```

or:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_factor_panel.ps1
```

Default scope:

```text
timerange = 20260101-
timeframe = 1h
pairs = auto-discovered local OKX USDT swap futures pairs
```

Outputs:

```text
reports/v13_4_21_factor_panel_report.json
reports/v13_4_21_factor_panel_summary.md
reports/v13_4_21_factor_panel_sample.json
reports/v13_4_21_manual_factor_library_report.json
docs/V13.4.21-factor-data-panel-implementation.md
docs/factor-data-panel-local-data-generation.md
docs/manual-factor-library-v01.md
docs/no-lookahead-factor-computation.md
```

The initial local V13.4.21 build generated:

```text
rowsGenerated = 124111
loadedPairs = 28
factorCount = 16
averageCoveragePct = 99.8435
```

Estimated fields are explicit:

```text
quoteVolume = close * volume
quoteVolumeEstimated = true
vwap = (high + low + close) / 3
vwapEstimated = true
```

V13.4.21 no-lookahead rules:

- rolling factors use only current and historical rows
- cross-sectional ranks are computed only within the same timestamp
- BTC relative strength context is timestamp-aligned
- forward labels and backtest outcomes do not enter factor values
- missing data remains null rather than being fabricated

V13.4.21 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no backtest execution
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.22 Factor Evaluation Report and Forward Label Analysis

V13.4.22 evaluates the V13.4.21 Manual Factor Library against forward-looking
research labels. It rebuilds the full local FactorDataPanel from public OHLCV,
adds 4 / 8 / 12 / 24 bar forward returns, MFE / MAE, and TP/SL first-touch
labels, then evaluates all 16 manual factors.

Run the evaluator:

```powershell
python -m alphapilot.factors.evaluate_factors
```

or:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\evaluate_factors.ps1
```

Default scope:

```text
timerange = 20260101-
timeframe = 1h
horizons = 4,8,12,24
TP = +5%
SL = -2.5%
quantiles = 5
```

Outputs:

```text
reports/v13_4_22_factor_evaluation_report.json
reports/v13_4_22_factor_evaluation_summary.md
reports/v13_4_22_factor_candidates.json
docs/V13.4.22-factor-evaluation-report.md
docs/factor-evaluation-methodology.md
docs/no-lookahead-forward-labels.md
docs/research-factor-vs-trading-signal.md
```

The initial V13.4.22 local evaluation generated:

```text
sampleCount = 124111
validLabelCount = 123439
evaluatedFactorCount = 16
candidateFactors = 0
```

Top research observations:

```text
Top absolute RankIC: volatility_3d, atr_pct, volatility_24h
Top Q5-Q1 spread: trend_strength, distance_to_ema50, volume_expansion_3d
Top profit factor: trend_strength, distance_to_ema50, atr_pct
```

No factor passed the V13.4.22 candidate gate. This is a research result, not a
failure of the pipeline. It means the current manual factors should not be
promoted directly into strategy entries or Dry-run candidates.

V13.4.22 no-lookahead rules:

- features are point-in-time
- labels are forward-looking for evaluation only
- labels never alter factor values, sample selection, or universe membership
- candidate factors are research artifacts, not trade signals

V13.4.22 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no strategy implementation
no backtest execution
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.23 Benchmark Strategy Suite

V13.4.23 implements the benchmark suite designed in V13.4.20 and runs it as a
local research baseline against public historical OHLCV.

Run the benchmark suite:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_benchmark_suite.ps1 -UseTop10 -Timerange "20260101-" -Run
python -m alphapilot.reports.generate_benchmark_suite_report
```

Implemented benchmarks:

```text
BenchmarkNoTrade
BenchmarkBuyHoldBTC
BenchmarkEMATrend
BenchmarkRSIMeanReversion
BenchmarkMACDVolume
BenchmarkBollingerRebound
BenchmarkTD9Exhaustion
```

Outputs:

```text
reports/v13_4_23_benchmark_manifest.json
reports/v13_4_23_benchmark_suite_report.json
reports/v13_4_23_benchmark_suite_summary.md
docs/V13.4.23-benchmark-strategy-suite.md
docs/benchmark-strategy-definitions.md
docs/benchmark-results-interpretation.md
```

The report compares each benchmark to:

```text
NoTrade baseline
BuyHoldBTC baseline
```

It also estimates one-way slippage stress at 0.05%, 0.10%, and 0.20% in
post-processing. Freqtrade itself does not apply that slippage in this version.

V13.4.23 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no Dry-run approval
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
benchmark results are not trading signals
```

## V13.4.24 Benchmark Result Review and Strategy Research Reset

V13.4.24 reviews the V13.4.23 benchmark suite output. It does not modify
benchmark strategy code and does not run a new backtest.

Generate the review:

```powershell
python -m alphapilot.reports.generate_benchmark_result_review
```

Outputs:

```text
reports/v13_4_24_benchmark_result_review.json
reports/v13_4_24_benchmark_result_summary.md
reports/v13_4_24_benchmark_status_archive.json
docs/V13.4.24-benchmark-result-review.md
docs/benchmark-failure-analysis.md
docs/no-trade-buyhold-baseline-importance.md
docs/strategy-research-reset-plan.md
```

Initial review conclusions:

```text
0/5 active benchmarks beat NoTrade
0/5 active benchmarks beat BuyHoldBTC
BenchmarkBollingerRebound is relative best but not usable
relative best != tradable
recommended next step: Strategy Research Factory / Factor Hypothesis Mining
```

V13.4.24 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no new backtest run
no benchmark strategy code changes
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.25 Strategy Research Factory

V13.4.25 converts prior research evidence into a structured hypothesis registry.
It reads the V13.4.22 factor evaluation report, V13.4.23 benchmark suite report,
and V13.4.24 benchmark result review.

Generate the factory report:

```powershell
python -m alphapilot.reports.generate_strategy_research_factory_report
```

Outputs:

```text
reports/v13_4_25_strategy_research_factory_report.json
reports/v13_4_25_strategy_research_factory_summary.md
reports/v13_4_25_research_hypotheses.json
docs/V13.4.25-strategy-research-factory.md
docs/factor-hypothesis-mining.md
docs/rejected-strategy-hypotheses.md
docs/next-experiment-plan.md
```

Hypothesis counts:

```text
total hypotheses: 14
research-only: 9
deferred: 1
rejected: 4
high priority: HYP-001, HYP-002, HYP-004, HYP-006, HYP-007, HYP-008
```

V13.4.25 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no strategy implementation
no backtest execution
no Dry-run
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.26 Factor Hypothesis Validation Dataset

V13.4.26 validates the high-priority research hypotheses from V13.4.25 against
a rebuilt full FactorDataPanel and forward labels.

Run the validator:

```powershell
python -m alphapilot.research_factory.validate_hypotheses
```

PowerShell wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\validate_hypotheses.ps1
```

Outputs:

```text
reports/v13_4_26_hypothesis_validation_report.json
reports/v13_4_26_hypothesis_validation_summary.md
reports/v13_4_26_hypothesis_validation_dataset_sample.json
reports/v13_4_26_hypothesis_recommendations.json
docs/V13.4.26-hypothesis-validation-dataset.md
docs/hypothesis-validation-methodology.md
docs/no-lookahead-hypothesis-validation.md
docs/hypothesis-support-vs-trading-approval.md
```

Validation result:

```text
sampleCount: 124111
validatedHypothesisCount: 6
topSupportedHypotheses: none
unsupportedHypotheses: HYP-001, HYP-002, HYP-004, HYP-006, HYP-007, HYP-008
hypothesesWithPositiveExcessVsBTC: HYP-002
nextStep: V13.4.27 - Research Direction Reset / Data Expansion
```

V13.4.26 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no strategy implementation
no backtest execution
no Dry-run
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.27 Market Regime and Data Integrity Review

V13.4.27 pauses the previous data expansion plan and first validates local
OHLCV integrity plus market regime context.

Run the review:

```powershell
python -m alphapilot.reports.generate_market_regime_data_integrity_review
```

Outputs:

```text
reports/v13_4_27_market_regime_data_integrity_report.json
reports/v13_4_27_market_regime_data_integrity_summary.md
reports/v13_4_27_btc_regime_labels.json
reports/v13_4_27_data_quality_by_pair.json
docs/V13.4.27-market-regime-data-integrity-review.md
docs/ohlcv-data-integrity-checks.md
docs/market-regime-labeling-methodology.md
docs/regime-aware-research-recommendation.md
```

Initial local result:

```text
status: completed_with_warnings
dataIntegrity.status: warning
pairCount: 30
pairTimeframeCount: 60
validCount: 55
warningCount: 1
invalidCount: 0
missingFileCount: 4
totalInvalidOhlcRows: 0
totalDuplicateTimestamps: 0
```

The review found no obvious OHLC corruption in the checked local files, but it
did find local coverage warnings and a strongly regime-sensitive BTC sample.
Recent long-only technical research failures should therefore be interpreted as
a combination of adverse bear/high-volatility context plus sparse validated
alpha, not as a single simple parameter issue.

V13.4.27 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no strategy implementation
no backtest execution
no data download
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
```

## V13.4.28 Market Data Coverage Repair and Public Data Expansion

V13.4.28 attempts to repair the V13.4.27 local OHLCV coverage warnings before
adding new market-context schemas. It also adds a public-data expansion
skeleton for Funding Rate, Open Interest, Orderbook Spread Proxy, Liquidation,
and Market Regime Proxy inputs.

Run the post-repair integrity review:

```powershell
python -m alphapilot.reports.generate_market_regime_data_integrity_review --output-report reports/v13_4_28_post_repair_market_regime_data_integrity_report.json --output-summary reports/v13_4_28_post_repair_market_regime_data_integrity_summary.md --output-btc-labels reports/v13_4_28_post_repair_btc_regime_labels.json --output-data-quality reports/v13_4_28_post_repair_data_quality_by_pair.json
```

Generate the V13.4.28 coverage and expansion reports:

```powershell
python -m alphapilot.reports.generate_market_data_expansion_report
```

Outputs:

```text
reports/v13_4_28_data_coverage_repair_report.json
reports/v13_4_28_data_coverage_repair_summary.md
reports/v13_4_28_post_repair_data_quality_by_pair.json
reports/v13_4_28_market_data_expansion_report.json
reports/v13_4_28_market_data_expansion_summary.md
docs/V13.4.28-market-data-coverage-repair-expansion.md
docs/funding-rate-data-design.md
docs/open-interest-data-design.md
docs/orderbook-spread-proxy-design.md
docs/market-data-source-registry.md
docs/data-quality-requirements.md
```

Current V13.4.28 result:

```text
status: completed_with_unresolved_gaps
preRepairMissingFileCount: 4
postRepairMissingFileCount: 4
unresolved files: FET/USDT:USDT 1h/4h, TON/USDT:USDT 1h/4h
remaining warning: ORDI/USDT:USDT 4h extreme close-to-close return review
```

The public data expansion is schema-only in V13.4.28. No funding, open
interest, orderbook, liquidation, or ticker collector is active yet. The data
source registry records public-only sources and keeps `requiresApiKey=false`
and `usesPrivateEndpoint=false`.

V13.4.28 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no strategy implementation
no backtest execution
no Dry-run
no Trade API / Withdraw API
no real API key
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.29 Short Rejection 1H Research Strategy

V13.4.29 adds a simple short-only 1h research strategy:

```text
AlphaPilot Short Rejection 1H V0.1
```

The strategy tests whether a rebound-failure short idea has research value in
the current local public OKX futures data. It does not treat bear regime as a
hard entry gate. It uses a small `shortScore` model and only a few hard
blockers.

Run smoke backtest:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_short_rejection_backtest.ps1 -Smoke -Run
```

Run expanded supported-pair backtest:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_short_rejection_backtest.ps1 -Expanded -UseSupportedPairs -Timerange "20260101-" -Run
```

Generate the report:

```powershell
python -m alphapilot.reports.generate_short_rejection_report
```

Outputs:

```text
reports/v13_4_29_short_rejection_1h_report.json
reports/v13_4_29_short_rejection_1h_summary.md
docs/V13.4.29-short-rejection-1h-research-strategy.md
docs/short-rejection-1h-strategy-rules.md
docs/short-strategy-risk-notes.md
```

Current result:

```text
smoke: 828 short trades, totalReturnPct -80.8628, profitFactor 0.6457
expanded: 5052 short trades, totalReturnPct -99.9966, profitFactor 0.782
expanded slippageAdjustedTotalReturnPct: -217.1225
expanded slippageAdjustedProfitFactor: 0.5966
maxDrawdownPct: 99.9966
researchWorthContinuing: false
```

Scope decisions:

```text
excludedPairs: FET/USDT:USDT, TON/USDT:USDT
watchlistPairs: ORDI/USDT:USDT
```

V13.4.29 remains research-only:

```text
dryRunApproved: false
liveTradingApproved: false
no Dry-run
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.30 Short Rejection Failure Review

V13.4.30 reviews the failed V13.4.29 short-only research strategy and archives it as:

```text
failed_research_current_sample
```

中文说明：

```text
V13.4.30 复盘 V13.4.29 做空研究策略失败结果，归档该策略为 failed_research_current_sample，并提炼后续做空研究的负样本规则。
本版本不调参、不回测、不进入 Dry-run、不接真实 API Key。
```

The source evidence is:

```text
reports/v13_4_29_short_rejection_1h_report.json
reports/v13_4_29_short_rejection_1h_summary.md
```

Generate the failure review:

```powershell
python -m alphapilot.reports.generate_short_rejection_failure_review
```

Outputs:

```text
reports/v13_4_30_short_rejection_failure_review.json
reports/v13_4_30_short_rejection_failure_summary.md
reports/v13_4_30_short_strategy_status_archive.json
reports/v13_4_30_negative_research_rules.json
docs/V13.4.30-short-rejection-failure-review.md
docs/short-strategy-negative-research-rules.md
docs/failed-strategy-archive-policy.md
docs/future-short-research-recommendations.md
```

Current conclusion:

```text
researchWorthContinuing: false
dryRunApproved: false
liveTradingApproved: false
nextStepRecommendation: V13.4.31 - Low-Frequency Mainstream Coin Research Plan
```

V13.4.30 remains report-only:

```text
no strategy modification
no new backtest
no Dry-run
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.31 Low-Frequency Mainstream Coin Research Plan

V13.4.31 narrows the next research track to BTC/ETH/SOL on 4h/1d timeframes.

中文说明：

```text
V13.4.31 将研究范围收窄到 BTC/ETH/SOL 的 4h/1d 低频方向，设计 long/short 均可研究的 regime-aware 低频研究计划。
本版本不写策略、不回测、不进入 Dry-run、不接 API Key。
```

Generate the research plan:

```powershell
python -m alphapilot.reports.generate_low_frequency_research_plan
```

Outputs:

```text
reports/v13_4_31_low_frequency_research_plan.json
reports/v13_4_31_low_frequency_research_summary.md
docs/V13.4.31-low-frequency-mainstream-research-plan.md
docs/low-frequency-research-hypotheses.md
docs/mainstream-coin-research-scope.md
docs/regime-aware-long-short-research.md
```

Research scope:

```text
pairs: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT
primaryTimeframes: 4h, 1d
optionalTimeframes: 1h
```

V13.4.31 defines five low-frequency research hypotheses:

```text
LF-HYP-001 BTC/ETH/SOL 4h Trend Following
LF-HYP-002 BTC/ETH/SOL 4h Bear Rejection Short
LF-HYP-003 1d Regime + 4h Entry
LF-HYP-004 Breakout Retest on Mainstream Coins
LF-HYP-005 NoTrade as Active Decision
```

Long and short can both be researched, but they must be evaluated separately.
Market regime is a direction-scoring and risk-weighting context, not the only
hard entry switch.

V13.4.31 remains research-plan-only:

```text
no strategy code
no data download
no backtest
no Dry-run
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.32 Low-Frequency Data Preparation and Baseline Builder

V13.4.32 prepares BTC/ETH/SOL 4h/1d public OHLCV data and builds report-only baseline references before any low-frequency strategy implementation.

中文说明：

```text
V13.4.32 只做低频数据准备和基线报告：
检查 BTC/ETH/SOL 的 4h/1d 本地公共 OHLCV 数据，
生成 NoTrade / BuyHold / EqualWeight 基线，
为后续低频策略研究建立最低比较标准。
```

Generate the reports:

```powershell
python -m alphapilot.reports.generate_low_frequency_baseline_report
```

Optional public OHLCV preparation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_low_frequency_baselines.ps1 -RunDownload -Prepend
```

Outputs:

```text
reports/v13_4_32_low_frequency_data_report.json
reports/v13_4_32_low_frequency_baseline_report.json
reports/v13_4_32_low_frequency_baseline_summary.md
docs/V13.4.32-low-frequency-data-baseline-builder.md
docs/low-frequency-data-quality-checks.md
docs/no-trade-buyhold-mainstream-baselines.md
docs/future-low-frequency-strategy-requirements.md
```

Baseline set:

```text
NoTrade
BuyHold BTC
BuyHold ETH
BuyHold SOL
EqualWeight BTC/ETH/SOL
```

V13.4.32 remains report-only:

```text
no strategy implementation
no Freqtrade strategy backtest
no Dry-run approval
no live trading approval
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.33 Low-Frequency Candidate Specification

V13.4.33 uses the V13.4.32 low-frequency baselines to define candidate strategy specs and baseline hurdles before any strategy code is written.

中文说明：

```text
V13.4.33 基于 V13.4.32 的低频基线，
设计 BTC/ETH/SOL 4h/1d 低频候选策略规格与 baseline hurdles。
本版本不写策略、不回测、不进入 Dry-run、不接 API Key。
```

Generate the candidate specification report:

```powershell
python -m alphapilot.reports.generate_low_frequency_candidate_spec_report
```

Outputs:

```text
reports/v13_4_33_low_frequency_candidate_spec_report.json
reports/v13_4_33_low_frequency_candidate_spec_summary.md
docs/V13.4.33-low-frequency-candidate-specification.md
docs/low-frequency-baseline-hurdles.md
docs/low-frequency-directional-score-framework.md
docs/v13_4_34_candidate-implementation-plan.md
```

Candidate specs:

```text
LF-CAND-A-4H-EMA-TREND-LONG
LF-CAND-B-4H-BEAR-REJECTION-SHORT
LF-CAND-C-1D-REGIME-4H-ENTRY-ROUTER
LF-CAND-D-4H-BREAKOUT-RETEST
LF-CAND-E-NOTRADE-DEFENSIVE-REGIME
```

V13.4.33 remains spec-only:

```text
no strategy implementation
no Freqtrade strategy backtest
no data download
no Dry-run approval
no live trading approval
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.34 Low-Frequency Directional 4H Research Strategy

V13.4.34 implements the first real low-frequency directional 4h research strategy and runs a local Freqtrade backtest for BTC/ETH/SOL.

中文说明：

```text
V13.4.34 实现 BTC/ETH/SOL 4h 多空低频研究策略，
执行真实本地 Freqtrade 回测，
并输出 baseline / slippage / regime / long-short 分解报告。
本版本结果为失败研究样本，不进入 Dry-run，不进入实盘。
```

Run the research backtest:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_low_frequency_directional_backtest.ps1 -Timerange "20240101-" -Run
python -m alphapilot.reports.generate_low_frequency_directional_report
```

Outputs:

```text
user_data/strategies/AlphaPilotLowFrequencyDirectional4HV01.py
user_data/backtest_results/v13_4_34_low_frequency_directional_4h.zip
reports/v13_4_34_low_frequency_directional_4h_report.json
reports/v13_4_34_low_frequency_directional_4h_summary.md
docs/V13.4.34-low-frequency-directional-4h-research-strategy.md
docs/low-frequency-directional-4h-strategy-rules.md
docs/low-frequency-directional-results-interpretation.md
```

Real backtest result:

```text
tradeCount: 2821
longTradeCount: 1312
shortTradeCount: 1509
totalReturnPct: -99.9659
slippageAdjustedTotalReturnPct: -150.0949
maxDrawdownPct: 99.9676
profitFactor: 0.6099
researchWorthContinuing: false
```

V13.4.34 remains research-only:

```text
no Dry-run approval
no live trading approval
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.4.35 Multi-Strategy Batch Research Backtest

V13.4.35 stops the single-strategy loop and tests eight low-frequency BTC/ETH/SOL 4h OHLCV-only strategy candidates in one research batch.

中文说明：

```text
V13.4.35 一次性实现 8 个低频 4h 研究策略，
批量运行真实本地 Freqtrade 回测，
统一生成 leaderboard / slippage / baseline 对比报告。
本轮所有策略均未通过研究继续门槛。
```

Run the batch:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_multi_strategy_batch_backtest.ps1 -UseMainstream -Timerange "20240101-" -Run
python -m alphapilot.reports.generate_multi_strategy_batch_report
```

Outputs:

```text
user_data/strategies/AlphaPilotLowFrequencyStrategyBatchV01.py
scripts/run_multi_strategy_batch_backtest.ps1
reports/v13_4_35_multi_strategy_batch_manifest.json
reports/v13_4_35_multi_strategy_batch_report.json
reports/v13_4_35_multi_strategy_batch_summary.md
docs/V13.4.35-multi-strategy-batch-backtest.md
docs/multi-strategy-batch-strategy-definitions.md
docs/multi-strategy-batch-results-interpretation.md
```

Batch result:

```text
realBacktestCount: 8
failedStrategies: 0
beatsNoTradeCount: 0
beatsEqualWeightCount: 0
researchWorthContinuingCount: 0
bestRawStrategy: AlphaPilotBatchH_VolatilityCompressionBreakout4H
bestRawReturnPct: -31.9496
bestSlippageAdjustedReturnPct: -49.6662
```

V13.4.35 remains research-only:

```text
no Dry-run approval
no live trading approval
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.5 Derivatives ML-Gated Strategy Pipeline

V13.5 pivots away from repeated OHLCV-only parameter tuning. It implements a
research-only derivatives feature panel, triple-barrier labeling, walk-forward
probability gate, and deterministic rule mining.

中文说明：

```text
V13.5 不再继续微调普通技术指标策略。
本版本建立衍生品特征 + 2R/1R 标签 + 概率门控 + 规则挖掘管线。
目标是把“胜率 > 55%、盈亏比接近 2:1”作为硬验收门槛。
未通过门槛，不进入模拟盘，不进入 Dry-run。
```

Run the V13.5 research pipeline:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_derivatives_ml_research.ps1 -Timeframe 4h -Run
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_derivatives_ml_research.ps1 -Timeframe 1h -Run
```

Outputs:

```text
alphapilot/derivatives/feature_panel.py
alphapilot/ml_gate/triple_barrier.py
alphapilot/ml_gate/probability_gate.py
alphapilot/reports/generate_v13_5_derivatives_ml_strategy_report.py
scripts/run_v13_5_derivatives_ml_research.ps1
reports/v13_5_derivatives_ml_strategy_4h_report.json
reports/v13_5_derivatives_ml_strategy_4h_summary.md
reports/v13_5_derivatives_ml_strategy_1h_report.json
reports/v13_5_derivatives_ml_strategy_1h_summary.md
docs/V13.5-derivatives-ml-gated-strategy-pipeline.md
docs/v13_5_strategy_decision_summary.md
```

Current decision:

```text
4h: no paper approval
1h: no paper approval
Dry-run: false
Live trading: false
Reason: no candidate passed the 55% win-rate and 2R hard gate
```

Closest findings:

```text
4h: ETH long continuation + neutral mark basis was historically useful but
failed on sample size, reward/risk, and recent robustness.

1h: SOL long continuation + low ATR had enough trades and win rate above 55%,
but failed on reward/risk and drawdown.
```

V13.5 remains research-only:

```text
no Dry-run approval
no live trading approval
no real API key
no Trade API / Withdraw API
no account / position reads
no real orders
no auto trading
no AlphaPilot Mobile App changes
```

## V13.5.1 Expanded Relaxed Derivatives Research

V13.5.1 expands the V13.5 pipeline to the locally available 28-pair OKX futures
universe and adds a relaxed shadow-watchlist gate.

中文说明：

```text
V13.5.1 按用户要求扩大测试币种，并略微放宽研究门槛。
但放宽后的候选仍然只是 research / forward-confirmation，不等于模拟盘或实盘批准。
```

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_1_expanded_relaxed_research.ps1 -Timeframe 1h -Run
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_1_expanded_relaxed_research.ps1 -Timeframe 4h -Run
```

Outputs:

```text
alphapilot/ml_gate/research_gates.py
alphapilot/reports/generate_v13_5_1_expanded_relaxed_research_report.py
scripts/run_v13_5_1_expanded_relaxed_research.ps1
reports/v13_5_1_expanded_relaxed_1h_report.json
reports/v13_5_1_expanded_relaxed_1h_summary.md
reports/v13_5_1_expanded_relaxed_4h_report.json
reports/v13_5_1_expanded_relaxed_4h_summary.md
docs/V13.5.1-expanded-relaxed-derivatives-research.md
```

Current V13.5.1 result:

```text
Loaded pairs: 28
Probability hard gate approved: false
Probability relaxed shadow-watchlist approved: false
Deterministic forward-confirmation candidate found: true
Paper approved: false
Dry-run approved: false
Live trading approved: false
```

Closest 4h deterministic mined candidate:

```text
Condition: BTC regime bear + return_3 > 6% + Bollinger z > 2.0
Trades: 166
Win rate: 60.8434%
Reward/risk: 1.9922
Profit factor: 3.0956
Max drawdown: 35.4801%
Holdout trades: 50
Holdout win rate: 56.0%
Holdout reward/risk: 1.9965
Holdout profit factor: 2.5411
Status: forward-confirmation only, not paper approved
```

Closest 1h deterministic mined candidate:

```text
Condition: short_reversal_candidate + BTC regime bull + relative_return_6 between -1% and 1%
Trades: 187
Win rate: 73.262%
Reward/risk: 1.2321
Profit factor: 3.3759
Max drawdown: 37.9023%
Holdout trades: 57
Holdout win rate: 70.1754%
Holdout reward/risk: 2.0235
Holdout profit factor: 4.7612
Status: forward-confirmation only, not paper approved
```

Interpretation:

```text
V13.5.1 found useful deterministic research candidates, but the probability-gated
walk-forward layer still did not pass. These candidates should be used for
forward-confirmation / shadow observation design, not paper or Dry-run execution.
```

## V13.5.2 Forward Confirmation and Local Paper Sandbox

V13.5.2 replays the V13.5.1 deterministic candidates as fixed rules and checks
their final holdout segment. This version introduces a local paper sandbox gate.

Important boundary:

```text
localPaperSandboxApproved = local simulated observation only
exchangeDryRunApproved = false
liveTradingApproved = false
```

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_2_forward_confirmation.ps1 -Run
```

Outputs:

```text
alphapilot/reports/generate_v13_5_2_forward_confirmation_report.py
scripts/run_v13_5_2_forward_confirmation.ps1
reports/v13_5_2_forward_confirmation_report.json
reports/v13_5_2_forward_confirmation_summary.md
reports/v13_5_2_forward_confirmation_signal_log.json
docs/V13.5.2-forward-confirmation-local-paper-sandbox.md
```

Current V13.5.2 decision:

```text
Local paper sandbox approved: true
Approved candidate: v13_5_1_1h_short_reversal_bull_relative_return
Exchange Dry-run approved: false
Live trading approved: false
```

Approved local paper candidate:

```text
Condition: short_reversal_candidate + BTC bull regime + relative_return_6 between -1% and 1%
Timeframe: 1h
Confirmation trades: 57
Confirmation win rate: 70.1754%
Confirmation reward/risk: 2.0235
Confirmation profit factor: 4.7612
Confirmation max drawdown: 11.9756%
```

Rejected candidate:

```text
4h BTC bear + return_3 > 6% + Bollinger z > 2.0
Reason: confirmation drawdown above 20%
```

V13.5.2 does not use API keys, does not call Trade API or Withdraw API, does
not read accounts or positions, does not create orders, and does not auto trade.

## V13.5.3 Local Paper Sandbox Ledger

V13.5.3 starts a local simulated ledger for the V13.5.2 approved candidate. It
uses local JSON signal logs only. It does not run Freqtrade exchange Dry-run,
does not connect to an exchange, does not use API keys, and does not create
orders.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_3_local_paper_sandbox.ps1 -Run
```

Outputs:

```text
alphapilot/paper_sandbox/local_paper_ledger.py
alphapilot/reports/generate_v13_5_3_local_paper_sandbox_report.py
scripts/run_v13_5_3_local_paper_sandbox.ps1
reports/v13_5_3_local_paper_sandbox_ledger.json
reports/v13_5_3_local_paper_sandbox_report.json
reports/v13_5_3_local_paper_sandbox_summary.md
docs/V13.5.3-local-paper-sandbox-ledger.md
```

Current V13.5.3 decision:

```text
Local paper sandbox started: true
Paper monitoring ready: true
Exchange Dry-run approved: false
Live trading approved: false
```

Default local paper ledger result:

```text
initialEquity: 10000
maxConcurrentPositions: 8
filledTrades: 41
winRate: 60.9756%
rewardRiskRatio: 1.6922
profitFactor: 2.644
totalReturnPct: 14.9788
maxDrawdownPct: 3.242758
```

The concurrency sensitivity table is included in the V13.5.3 summary. Lower
caps such as 3 and 5 positions were too restrictive for this clustered
multi-pair signal. `maxConcurrentPositions=8` is the first tested cap that
passes the local paper monitoring gate.

V13.5.3 remains local simulation only:

```text
no Trade API
no Withdraw API
no API key storage
no real account reads
no real position reads
no real orders
no automatic trading
exchange Dry-run remains disabled
```

## V13.5.4 Local Paper Monitoring and Fresh Evidence Refresh

V13.5.4 turns the V13.5.3 one-shot local paper ledger into a repeatable local
monitoring pipeline. It can optionally refresh public 1h market data, rerun the
V13.5.2 forward-confirmation signal log, rerun the V13.5.3 local paper ledger,
and generate a V13.5.4 monitoring report with rolling windows, freshness checks,
skipped-signal analysis, and decay warnings.

Important boundary:

```text
localPaperMonitoringActive = local simulated observation only
exchangeDryRunReviewReady = false
liveTradingApproved = false
```

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_4_local_paper_monitoring.ps1 -RefreshPublicData
```

Run with public data refresh:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_4_local_paper_monitoring.ps1 -RefreshPublicData -Run
```

Outputs:

```text
alphapilot/paper_sandbox/paper_monitoring.py
alphapilot/reports/generate_v13_5_4_local_paper_monitoring_report.py
scripts/run_v13_5_4_local_paper_monitoring.ps1
reports/v13_5_4_local_paper_monitoring_report.json
reports/v13_5_4_local_paper_monitoring_summary.md
reports/v13_5_4_local_paper_monitoring_events.json
docs/V13.5.4-local-paper-monitoring.md
```

Current V13.5.4 decision:

```text
Local paper monitoring active: true
Monitoring health: watch
Continue local paper monitoring: true
Exchange Dry-run review ready: false
Live trading approved: false
Reason: local_paper_monitoring_continues_with_decay_warnings
```

Full local paper ledger metrics:

```text
filledTrades: 41
winRate: 60.9756%
rewardRiskRatio: 1.6922
profitFactor: 2.644
totalReturnPct: 14.9788
maxDrawdownPct: 3.242758
maxConsecutiveLosses: 3
```

Recent-window warnings:

```text
last 10 trades: winRate=50.0%, rewardRisk=1.1522, profitFactor=1.1522
last 20 trades: winRate=50.0%, rewardRisk=1.3738, profitFactor=1.3738
closed fill freshness: stale
signal-to-closed-fill lag: above 5 days
some approved signals skipped by max concurrent position cap
```

V13.5.4 public data refresh extended the local 1h OKX futures data through
`2026-07-05 16:00 UTC` for the checked BTC/ETH/SOL files. The monitoring report
still does not approve exchange Dry-run because recent closed-fill evidence is
not fresh enough and the recent 10/20-trade windows show decay.

V13.5.4 remains local simulation only:

```text
no Trade API
no Withdraw API
no API key storage
no real account reads
no real position reads
no real orders
no automatic trading
exchange Dry-run remains disabled
```

## V13.5.5 Event Pool Expansion

V13.5.5 expands the amount of public historical data converted into candidate
events. It is an anti-overfit research checkpoint: broad sample coverage,
pair/month concentration, and recent holdout size are reported separately from
headline win-rate metrics.

Important boundary:

```text
eventPoolExpanded = public historical data research only
newLocalPaperCandidateApproved = false
exchangeDryRunApproved = false
liveTradingApproved = false
```

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_5_event_pool_expansion.ps1
```

Refresh public data and generate the event-pool report:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_5_event_pool_expansion.ps1 -RefreshPublicData -Prepend -Run
```

Generate from existing local data:

```powershell
python -m alphapilot.reports.generate_v13_5_5_event_pool_expansion_report
```

Outputs:

```text
alphapilot/reports/generate_v13_5_5_event_pool_expansion_report.py
scripts/run_v13_5_5_event_pool_expansion.ps1
reports/v13_5_5_event_pool_expansion_report.json
reports/v13_5_5_event_pool_expansion_summary.md
reports/v13_5_5_event_pool_candidates.json
docs/V13.5.5-event-pool-expansion.md
```

V13.5.5 does not optimize parameters to chase a target win rate. It lowers the
event-pool win-rate screen to `45%` while keeping the `2R` reward/risk target
unchanged. Profit factor, drawdown, total return, sample breadth, and holdout
checks still have to pass before any pool can become a forward-confirmation
candidate.

The default V13.5.5 report uses `1h` and `4h`. `15m` can be supplied manually,
but it is not the default because it is substantially heavier and more prone to
short-term noise.

V13.5.5 remains research-only:

```text
no Trade API
no Withdraw API
no API key storage
no real account reads
no real position reads
no real orders
no automatic trading
exchange Dry-run remains disabled
```

## V13.5.6 High Reward Event Redesign

V13.5.6 keeps the target at `2R` and redesigns event definitions toward
structures that can naturally support higher reward/risk. This is not a
parameter-optimization pass. It adds high-reward event hypotheses, labels them
with the existing triple-barrier simulator, and reports whether any pool has
enough breadth and recent stability to deserve forward confirmation.

Important boundary:

```text
targetRMultiple = 2.0
newLocalPaperCandidateApproved = report result only
exploratoryLocalPaperWatchApproved = report result only
exchangeDryRunApproved = false
liveTradingApproved = false
```

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_6_high_reward_event_redesign.ps1
```

Generate from existing local data:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_6_high_reward_event_redesign.ps1 -Run
```

Outputs:

```text
alphapilot/ml_gate/high_reward_event_setups.py
alphapilot/ml_gate/high_reward_triple_barrier.py
alphapilot/reports/generate_v13_5_6_high_reward_event_redesign_report.py
scripts/run_v13_5_6_high_reward_event_redesign.ps1
reports/v13_5_6_high_reward_event_redesign_report.json
reports/v13_5_6_high_reward_event_redesign_summary.md
reports/v13_5_6_high_reward_candidates.json
docs/V13.5.6-high-reward-event-redesign.md
```

V13.5.6 reports the cost-adjusted net reward/risk ceiling because roundtrip fee
and slippage reduce observed net winners and deepen observed net losses. This
is an accounting clarification, not a relaxation of the `2R` target.

If a fixed exploratory filter clears the local watch screen, it is only approved
for local paper observation. It is not approved for exchange Dry-run, live
trading, order creation, or automatic execution.

V13.5.6 remains research-only:

```text
no Trade API
no Withdraw API
no API key storage
no real account reads
no real position reads
no real orders
no automatic trading
exchange Dry-run remains disabled
```

## V13.5.7 External Alpha Overlay Research

V13.5.7 reviews two public GitHub projects as concept references and adds an
Alpha101-style factor overlay to the existing high-reward event research
pipeline.

External references:

```text
yydhYYDH/alpha101
ryckli/CryptoAgentPro.beta
```

AlphaPilot only stores URL/license/summary/citation metadata for these
references. It does not copy external code or long source text.

The overlay adds:

```text
cross-sectional ranks
time-series ranks
rolling return-volume correlation
decay-style return and volume pressure
rebound pressure
exhaustion pressure
liquidity quality
```

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_7_external_alpha_overlay.ps1
```

Generate from existing local public data:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_7_external_alpha_overlay.ps1 -Run
```

Outputs:

```text
alphapilot/factors/alpha101_style_overlay.py
alphapilot/reports/generate_v13_5_7_external_alpha_overlay_report.py
scripts/run_v13_5_7_external_alpha_overlay.ps1
reports/v13_5_7_external_alpha_overlay_report.json
reports/v13_5_7_external_alpha_overlay_summary.md
reports/v13_5_7_alpha_overlay_candidates.json
docs/V13.5.7-external-alpha-overlay.md
```

Current V13.5.7 decision:

```text
localPaperWatchApproved = true
localPaperWatchPoolId = 4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24
newFormalPaperCandidateApproved = false
exchangeDryRunApproved = false
liveTradingApproved = false
```

Best overlay pool:

```text
trades = 145
winRate = 58.6207%
rewardRiskRatio = 1.8207
profitFactor = 2.5793
maxDrawdown = 38.3157%
recent20ProfitFactor = 3.2286
observedToCostAdjusted2RCloseness = 0.956639
```

Interpretation: V13.5.7 finds a useful 4h short-exhaustion local paper watch
pool, but drawdown remains high and the result requires fresh forward
confirmation. It is not approved for exchange Dry-run or live trading.

V13.5.7 remains research-only:

```text
no Trade API
no Withdraw API
no API key storage
no real account reads
no real position reads
no real orders
no automatic trading
exchange Dry-run remains disabled
```

## V13.5.8 Adaptive ML Factor Discovery

V13.5.8 adds an auditable adaptive machine-learning layer. It lets AlphaPilot
learn factor-threshold rules from prior folds and validate those rules on later
folds. This creates a foundation for strategy evolution without granting the
model any trading authority.

The current runtime does not include sklearn/xgboost/lightgbm/catboost, so
V13.5.8 uses a lightweight pandas/numpy learner:

```text
train-only context discovery
factor quantile thresholds
walk-forward validation
fold stability checks
strategy evolution sample schema
```

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_8_adaptive_ml_factor_report.ps1
```

Generate from existing local public data:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_8_adaptive_ml_factor_report.ps1 -Run
```

Outputs:

```text
alphapilot/ml_gate/adaptive_factor_learner.py
alphapilot/ml_gate/strategy_evolution_schema.py
alphapilot/reports/generate_v13_5_8_adaptive_ml_factor_report.py
scripts/run_v13_5_8_adaptive_ml_factor_report.ps1
reports/v13_5_8_adaptive_ml_factor_report.json
reports/v13_5_8_adaptive_ml_factor_summary.md
reports/v13_5_8_adaptive_ml_candidates.json
reports/v13_5_8_strategy_evolution_sample_schema.json
docs/V13.5.8-adaptive-ml-factor-discovery.md
```

Current V13.5.8 decision:

```text
adaptiveMLComputed = true
targetRMultipleUnchanged = true
localPaperWatchApproved = false
localPaperWatchPoolId = null
newFormalPaperCandidateApproved = false
exchangeDryRunApproved = false
liveTradingApproved = false
```

Best full adaptive candidate:

```text
pool = 1h:adaptive_ml_all_high_reward:sl0.025:h30
selectedTrades = 1275
winRate = 36.7059%
rewardRiskRatio = 1.6143
profitFactor = 0.9362
totalReturn = -86.5794%
maxDrawdown = 98.3195%
```

Interpretation: the adaptive learner improved some baselines and found
positive small-sample rules, but the full walk-forward candidate is still
negative. V13.5.8 does not approve a new local paper watch candidate. The
current actionable research line remains the V13.5.7 fixed 4h alpha overlay,
which still requires fresh forward confirmation.

V13.5.8 also adds `strategy_evolution_sample_v1` so future local paper outcomes
and manual trade-review outcomes can become research samples. These samples can
only support offline retraining after validation; they must not trigger order
creation or bypass risk review.

V13.5.8 remains research-only:

```text
no Trade API
no Withdraw API
no API key storage
no real account reads
no real position reads
no real orders
no automatic trading
exchange Dry-run remains disabled
```

## Future Live Trading Reference Notes

The repository now stores a reference-only design note for
`ryckli/CryptoAgentPro.beta`:

```text
docs/future-live-trading-reference-cryptoagentpro-beta.md
```

It records future-review concepts such as API key configuration, order
endpoints, emergency close, testnet mode, automatic mode, risk gateway,
strategy scheduling, and AI trend analysis. This is documentation only. It does
not add Trade API, Withdraw API, exchange credentials, account reads, position
reads, order creation, emergency close, testnet execution, or automatic trading.

The repository also stores a reference-only note for `yydhYYDH/alpha101`:

```text
docs/future-factor-research-reference-alpha101.md
```

This records factor-panel, expression-grammar, factor-search, IC-style
evaluation, and research-service ideas for future AlphaPilot factor work. It
does not import alpha101, copy source code, create strategies, or approve
execution.

The combined external reference index is:

```text
docs/external-repository-reference-index.md
```

## V13.5.9 Strategy Control Tower and Local Paper Router

V13.5.9 adds a local-paper-only control tower that coordinates existing research
outputs into strategy states and router intents.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_9_strategy_control_tower.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_9_strategy_control_tower.ps1 -Run
```

Outputs:

```text
alphapilot/control_tower/strategy_control_tower.py
alphapilot/reports/generate_v13_5_9_strategy_control_tower_report.py
scripts/run_v13_5_9_strategy_control_tower.ps1
reports/v13_5_9_strategy_control_tower_report.json
reports/v13_5_9_strategy_control_tower_summary.md
reports/v13_5_9_local_paper_router_intents.json
reports/v13_5_9_external_reference_index.json
docs/V13.5.9-strategy-control-tower-local-paper-router.md
```

V13.5.9 current routing decision:

```text
V13.5.7 alpha overlay = active local paper watch
V13.5.8 adaptive ML = observer only
exchange Dry-run review = not ready
live trading = not approved
```

Router intents are not orders. V13.5.9 does not add Trade API, Withdraw API,
exchange credentials, account reads, position reads, order creation, emergency
close, testnet execution, or automatic trading.

## V13.5.10 Continuous Learning Loop

V13.5.10 starts the AlphaPilot continuous learning loop by converting local
paper outcomes into strategy evolution samples and a retraining-readiness gate.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_10_continuous_learning_loop.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_10_continuous_learning_loop.ps1 -Run
```

Outputs:

```text
alphapilot/learning_loop/strategy_learning_loop.py
alphapilot/reports/generate_v13_5_10_continuous_learning_loop_report.py
scripts/run_v13_5_10_continuous_learning_loop.ps1
reports/v13_5_10_continuous_learning_loop_report.json
reports/v13_5_10_continuous_learning_loop_summary.md
reports/v13_5_10_strategy_evolution_dataset.json
reports/v13_5_10_learning_state.json
docs/V13.5.10-continuous-learning-loop.md
```

Current learning-loop result:

```text
newTrainingSamplesFromPaper = 41
usableTrainingSamplesFromPaper = 41
activeStrategySamplesFromPaper = 0
readyForRetraining = false
continueLocalPaperMonitoring = true
exchange Dry-run = not approved
live trading = not approved
```

The 41 available paper samples belong to an older V13.5.1 candidate. The current
V13.5.7 active local paper watch has no closed paper samples yet, so V13.5.10
does not retrain a model.

Future data expansion can include larger public sample pools across crypto,
A-shares, Hong Kong stocks, US equities, ETFs, and indices. Cross-market samples
must be stored as research data with explicit labels and must not become crypto
execution commands.

V13.5.10 does not add Trade API, Withdraw API, API key storage, real account
reads, real position reads, real orders, emergency close, testnet execution, or
automatic trading.

## V13.5.11 Cross-Market Public Data Smoke

V13.5.11 adds a public cross-market data smoke test so AlphaPilot can begin
expanding its research sample base beyond crypto.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_11_cross_market_data_smoke.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_11_cross_market_data_smoke.ps1 -Run
```

Outputs:

```text
alphapilot/cross_market/public_market_data.py
alphapilot/reports/generate_v13_5_11_cross_market_data_smoke_report.py
scripts/run_v13_5_11_cross_market_data_smoke.ps1
reports/v13_5_11_cross_market_public_data_smoke_report.json
reports/v13_5_11_cross_market_public_data_smoke_summary.md
docs/V13.5.11-cross-market-public-data-smoke.md
user_data/cross_market_data/
```

Default smoke symbols cover A-share, Hong Kong, US ETF, and index references:

```text
600519.SS, 000001.SZ, 0700.HK, 9988.HK, SPY, QQQ, ^HSI, ^GSPC
```

Raw OHLCV files are cached locally under `user_data/cross_market_data/` and are
not committed to Git. Cross-market samples are research references for regime,
volatility, liquidity, and factor robustness. They are not crypto execution
commands and they do not approve exchange Dry-run or live trading.

V13.5.11 does not add Trade API, Withdraw API, API key storage, broker
credentials, real account reads, real position reads, real orders, or automatic
trading.

## V13.5.12 Active Alpha Overlay Replay

V13.5.12 rebuilds the current V13.5.7 active alpha overlay pool into a
single-trade event log and replays it through the local paper sandbox.

Run preview:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_12_active_alpha_overlay_replay.ps1
```

Generate reports:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_v13_5_12_active_alpha_overlay_replay.ps1 -Run
```

Outputs:

```text
alphapilot/reports/generate_v13_5_12_active_alpha_overlay_replay_report.py
scripts/run_v13_5_12_active_alpha_overlay_replay.ps1
reports/v13_5_12_active_alpha_overlay_replay_report.json
reports/v13_5_12_active_alpha_overlay_replay_summary.md
reports/v13_5_12_active_alpha_overlay_signal_log.json
reports/v13_5_12_active_alpha_overlay_paper_ledger.json
docs/V13.5.12-active-alpha-overlay-replay.md
```

Current result:

```text
activeOverlayEventCount = 145
filledSignalCount = 131
tradeCount = 131
winRate = 58.7786%
profitFactor = 2.5656
rewardRiskRatio = 1.7992
maxDrawdown = 6.82632%
```

This is the first active-strategy replay that looks operationally useful. It is
still historical replay, not forward validation. The next gate is fresh forward
local paper monitoring after the active pool selection date.

V13.5.12 does not add Trade API, Withdraw API, API key storage, real account
reads, real position reads, real orders, exchange Dry-run execution, live
trading, or automatic trading.

## Next Versions

- V13.4.28 follow-up: resolve remaining FET/TON OHLCV coverage policy before strategy specification.
- V13.5.13: collect fresh public crypto data and run forward local paper monitoring for the V13.5.7 4h alpha overlay after the pool selection date.
- V13.5.14: expand cross-market feature normalization and data quality scoring before using non-crypto samples in any model review.
- V13.5.15: consider independent Binance/Bybit public-data expansion before any exchange Dry-run review.
- V13.6: consider exchange Dry-run candidate evaluation only after local paper validation is fresh, stable, broad, and reviewed.
