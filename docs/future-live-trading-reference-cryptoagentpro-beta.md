# Future Live Trading Reference: CryptoAgentPro.beta

Status: reference-only
Source repo: https://github.com/ryckli/CryptoAgentPro.beta
Source license: MIT License, copyright 2026 RuiQi Li
Recorded at: 2026-07-06

This document records live-trading-adjacent concepts from CryptoAgentPro.beta for future AlphaPilot design work. It does not implement any of these capabilities in AlphaPilot.

## Why This Is Recorded

CryptoAgentPro.beta is useful as a future architecture reference because it combines:

- public market data collection and backtesting
- paper and testnet mode separation
- strategy scheduling
- AI trend analysis
- human confirmation before sensitive actions
- risk checks before order flow
- execution endpoints and emergency controls

AlphaPilot should learn from the system boundaries and safety structure, not copy execution behavior into the current research branch.

## Source Metadata

| Field | Value |
|---|---|
| Repository | `ryckli/CryptoAgentPro.beta` |
| URL | https://github.com/ryckli/CryptoAgentPro.beta |
| License | MIT |
| Summary | Crypto trading agent system with strategies, backtesting, paper/testnet modes, AI trend analysis, risk gateway, and execution-related endpoints. |
| Citation | GitHub README and LICENSE viewed on 2026-07-06. |

Only URL, license, summary, and citation-style metadata are stored here. Do not copy large source passages into AlphaPilot.

## Capability Inventory For Future Review

### 1. API Key Configuration

Reference concept:

- exchange credential configuration
- AI provider credential configuration
- environment-based setup
- front-end configurable settings in the reference system

AlphaPilot future requirement:

- never store raw exchange credentials in plain SQLite or repo files
- require encrypted local vault or OS credential store if credentials are ever supported
- separate testnet credentials from live credentials
- use least-privilege exchange scopes
- disallow withdrawal permission
- require explicit user confirmation before any credential becomes active
- show permission audit status before execution features unlock

Current AlphaPilot status:

- not implemented
- no exchange API key input
- no raw API key storage

### 2. `/trade/order`-Style Order Endpoint

Reference concept:

- an API endpoint for creating orders through an execution layer
- strategy output can become an executable action after checks

AlphaPilot future requirement:

- must not exist until a separate live-trading design boundary is approved
- every request must pass risk gateway, permission gateway, idempotency check, and human confirmation
- every request must create a full audit record before any exchange call
- order intent must be separate from order execution
- rejected intents must be preserved for review
- default mode must remain paper/testnet until live mode is explicitly unlocked

Current AlphaPilot status:

- not implemented
- no order endpoint
- no exchange execution path

### 3. Emergency Close / Kill Switch

Reference concept:

- emergency close endpoint or control for fast risk reduction

AlphaPilot future requirement:

- must be treated as a high-risk execution feature
- must verify open positions from a permitted account source
- must require explicit user confirmation unless a separately approved emergency policy exists
- must write audit logs before and after action
- must include rate limits and duplicate prevention
- must include a global kill switch that disables all further execution attempts

Current AlphaPilot status:

- not implemented
- no real position reads
- no emergency execution control

### 4. Testnet Mode

Reference concept:

- sandbox/testnet trading with exchange testnet credentials
- separate from local paper simulation

AlphaPilot future requirement:

- testnet must be isolated from live mode
- testnet credentials must not be reusable for live mode
- UI must clearly label sandbox state
- testnet order flow must still pass the same risk gateway
- testnet results must not be presented as real performance

Current AlphaPilot status:

- not implemented
- current local paper watch is not exchange testnet

### 5. Automatic Mode

Reference concept:

- optional automatic strategy switching or execution after AI/strategy checks

AlphaPilot future requirement:

- must remain disabled until paper and testnet evidence is strong
- must require separate user approval, not a hidden default
- must include daily loss limits, per-trade risk limits, max order count, cooldown, kill switch, and audit replay
- must never allow withdrawal permission
- should only be considered after human-confirmed semi-auto proves stable

Current AlphaPilot status:

- not implemented
- no automatic trading

## Other Architecture Ideas Worth Reusing

### Risk Gateway First

Every future execution-adjacent feature should route through a risk gateway before it can reach any execution adapter.

Required checks:

- max risk per intent
- daily loss limit
- available margin policy
- leverage cap
- duplicate signal prevention
- stale market data check
- slippage and liquidity gate
- emergency disabled state

### Human Confirmation Layer

AI and strategy components can produce candidate context, but user confirmation must be a separate gate.

Recommended future model:

```text
research signal
-> paper intent
-> risk gateway
-> human confirmation
-> testnet intent
-> testnet execution
-> audited result
```

Live execution, if ever added, must be a later and separately approved stage.

### Strategy Scheduler

The reference system maps market states to strategy families. AlphaPilot can adapt this idea as a research-only scheduler:

- trend-following candidate family
- mean-reversion candidate family
- volatility breakout candidate family
- crash rebound candidate family
- liquidity rejection candidate family

The scheduler should select research candidates, not orders.

### Backtest Progress And Speed Controls

The reference system includes progress and speed concepts for backtests. AlphaPilot can reuse the idea for UI/reporting:

- backtest task id
- progress percentage
- current step
- estimated remaining time
- speed profile for display only

This should not change signal rules or create execution authority.

### AI Trend Analysis

The reference system uses periodic AI trend analysis. AlphaPilot can adapt this only as a report layer:

- summarize latest public market state
- explain active research candidates
- compare against historical paper outcomes
- suggest what evidence is missing

AI must not own money or execute trades.

### Compact Kline Context

The reference system uses compact candle context. AlphaPilot can keep a similar idea for AI prompt compression:

- close/open relation
- previous close relation
- high/low range
- candle direction marker

This is for analysis context only.

## Future AlphaPilot Phase Gate

Before any of these reference capabilities can become real AlphaPilot features, the following gates must pass:

1. Local paper ledger has enough fresh closed outcomes.
2. Strategy has stable walk-forward and recent-window behavior.
3. Slippage and liquidity gate is explicit.
4. Risk gateway exists and is tested.
5. Credential storage design is approved.
6. Testnet-only execution adapter is implemented and audited.
7. Human confirmation is mandatory.
8. Withdrawal permission is impossible by design.
9. Live mode remains locked behind a separate version boundary.

## Explicit Current Boundary

This reference document does not add:

- Trade API
- Withdraw API
- exchange API key input
- exchange API key storage
- real account reads
- real position reads
- real order creation
- emergency close execution
- testnet order execution
- automatic trading

It only preserves design notes for future review.
