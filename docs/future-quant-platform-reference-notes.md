# Future Quant Platform Reference Notes

Status: reference-only
Recorded at: 2026-07-07
Scope: platform architecture, research workflow, backtest UX, safety boundaries

This note records external open-source and public article references that may
help AlphaPilot evolve from a strategy research engine into a full research
control platform. It does not install dependencies, copy external source code,
or enable trading.

## Source Metadata

| Source | URL | License / rights note | Stored content |
|---|---|---|---|
| QuantFans/quantdigger | https://github.com/QuantFans/quantdigger | License was not clearly surfaced in the GitHub page snapshot reviewed here; treat as reference-only until license is verified from the repository tree. | URL, summary, architecture notes, citation. |
| HelloGitHub issue #3107 about QuantDinger | https://github.com/521xueweihan/HelloGitHub/issues/3107 | GitHub issue content; use as discovery metadata only. | URL, summary, citation. |
| brokermr810/QuantDinger | https://github.com/brokermr810/QuantDinger | Apache-2.0 license shown on repository page. | URL, summary, architecture notes, citation. |
| Sina quant open-source roundup | https://cj.sina.com.cn/articles/view/7857141524/1d452771401901oj1w?froms=ggmp | Public article; do not copy article text beyond brief citation/summary. | URL, categorized tool radar, citation. |

## Useful Ideas for AlphaPilot

### 1. Event-Driven Backtest Contract

QuantDigger is useful as a reference for an event-driven strategy lifecycle:

- initialize strategy state
- process each bar
- update position state
- produce deals / marks / equity curve
- summarize results after the run

AlphaPilot should not copy QuantDigger code. The useful takeaway is the contract
shape: strategy modules should expose explicit lifecycle hooks and return
structured event records that the console can render as signal tape, fills,
equity, and diagnostics.

Recommended AlphaPilot adaptation:

- `StrategySpec` for parameters and required data.
- `StrategyRuntimeState` for warmup, position, and risk gate state.
- `StrategyEvent` for signal, skip, fill, exit, and risk-block events.
- `BacktestRunArtifact` for equity curve, trades, metrics, and charts.

### 2. Strategy + Portfolio Layer

QuantDigger's demo material emphasizes multiple strategies and combined equity.
AlphaPilot should keep this as a future platform layer:

- run one strategy against many symbols
- run many strategies against one universe
- aggregate paper observations into portfolio-level exposure
- report strategy-level and portfolio-level drawdown separately

This is directly relevant to the desktop console panel that should show
strategy, signal, simulated/paper position context, and backtest result in one
screen.

### 3. Local-First AI Trading OS Boundary

QuantDinger is useful as a modern architecture reference, especially the
separation between:

- self-hosted backend
- web console
- mobile/H5 client
- agent gateway
- audit logs
- paper-first / live-trading locked execution model

AlphaPilot should adapt the pattern, not the implementation. The important
boundary is that agent or AI actions should be scoped, auditable, and disabled
from live execution until a separate explicit unlock design exists.

Recommended AlphaPilot adaptation:

- keep the desktop console as the operator dashboard
- keep the phone app as the command console
- add an audit-first agent gateway only after paper/shadow trading is reliable
- keep all trading-class actions disabled by default
- require separate server-side and user-side unlocks before any future live path

### 4. Tool Radar From Public Roundup

The Sina roundup is useful as a map of categories, not as implementation truth.
The relevant categories for AlphaPilot are:

- quant frameworks: vn.py, Qlib, QUANTAXIS, RQAlpha, WonderTrader, Superalgos
- backtest engines: Zipline, Backtrader
- data/factor tools: yfinance, TA-Lib, TuShare, AKShare
- crypto execution systems: Hummingbot
- research AI frameworks: FinRL, TF Quant Finance

AlphaPilot should prioritize:

1. data quality and replayability
2. benchmark and baseline rigor
3. strategy runtime artifacts
4. paper/shadow observation ledger
5. agent/audit boundaries

It should not jump directly to execution bots or UI automation tools.

## Candidate Roadmap Inputs

### Near Term

- Add a formal strategy lifecycle contract for AlphaPilot strategy modules.
- Extend runtime status with strategy event counts by type.
- Add a backtest artifact index that the desktop and mobile consoles can read.
- Add portfolio-level paper observation summaries without exchange access.

### Mid Term

- Build an agent-readable research API that is read-only by default.
- Add audit logs for every AI/agent request.
- Add paper-only command scopes before any live trading design.
- Add external data adapter interfaces for AKShare/yfinance-style historical
  research, while keeping crypto execution logic separate.

### Later Boundary Work

- API key vault and exchange permissions must be a separate design boundary.
- Trade API, Withdraw API, live account reads, live position reads, order
  creation, and automatic trading remain disabled until that boundary exists.
- Any future live mode must require explicit user confirmation, scoped tokens,
  rate limits, emergency stops, and append-only audit trails.

## Do Not Copy Yet

Do not copy source files from these projects into AlphaPilot. If a future task
uses a specific implementation idea, first verify its license, isolate the
design pattern, and rewrite the AlphaPilot implementation to match our own
runtime contract and safety model.

## Safety Boundary

This note adds no:

- dependency
- data download
- external code execution
- API key input or storage
- Trade API
- Withdraw API
- real account reads
- real position reads
- order creation
- dry-run execution
- live trading
- automatic trading
