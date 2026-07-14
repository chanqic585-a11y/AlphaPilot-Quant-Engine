# Local Formal Backtest Design

## Decision

AlphaPilot formal backtests use only historical files already present under `D:\Codex-Workspace\回测数据`. The workflow must never call an exchange history endpoint or start an automatic history download.

## Data Flow

1. Discover the user-approved local OHLCV and funding files.
2. Select up to 50 swap symbols with complete coverage for the strategy signal, execution, fallback and funding requirements. Prefer BTC, ETH and SOL, then rank by longest local coverage.
3. Reuse immutable canonical files when their source identity is unchanged; otherwise convert the existing local file to a canonical Parquet file.
4. Freeze a content-hashed snapshot labelled `user_approved_local_market_data`.
5. Run the existing walk-forward, holdout, locked OOS, regime, cost-stress and target-R gates unchanged.

## Missing Data

Missing local files block the workflow with an explicit local-data gap. They do not trigger a network request. The user can add files to the warehouse and retry the same strategy version.

## Compatibility

Existing workflow phase identifiers remain unchanged so paused and queued runs can resume safely. Their display labels and evidence source change from OKX official download wording to local formal data wording. Partial official-download checkpoints remain on disk but are no longer consulted by the default workflow.

## Safety

This change affects historical research only. It does not add API keys, private exchange endpoints, orders, Withdraw, account reads, position reads, Demo bypasses or live-trading approval.
