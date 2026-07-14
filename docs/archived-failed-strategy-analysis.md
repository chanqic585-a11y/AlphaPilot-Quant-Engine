# Archived Failed Strategy Analysis

This research layer converts AlphaPilot's archived strategy evidence into a
single auditable failure inventory. It reads the existing status archives,
structured reports, and locally available backtest artifacts. It does not run
new backtests or modify any strategy.

## Current inventory

The first inventory contains 13 records:

- 6 Volume Rebound V01/V02 records rejected for Dry-run.
- 5 failed or negative benchmark strategies plus the explicitly rejected
  Martingale benchmark idea.
- 1 Short Rejection 1H strategy that failed the expanded sample.

`NoTrade` and `BuyHold BTC` remain comparison baselines and are intentionally
excluded from the failed-strategy count.

## Generate

```powershell
.venv\Scripts\python.exe -m alphapilot.reports.generate_archived_strategy_failure_analysis
```

The command writes the inventory, normalized metrics matrix, attribution
matrix, negative rules, reusable components, revival criteria, CSV exports,
and Chinese summary under `reports/`.

## Important semantics

- `null` means the source evidence does not provide the value.
- Numeric zero is retained only when the source actually recorded zero.
- Evidence level 1 means a referenced raw backtest artifact exists locally.
- Evidence level 2 means a structured JSON report exists without a local raw
  artifact.
- Evidence levels 3 and 4 are documentation/code-only evidence and cannot
  support execution promotion.
- Failure attribution is descriptive. It does not prove a single causal
  mechanism.

## Safety boundary

Every archived record remains non-executable. This analysis does not change
Dry-run, Demo, Live, risk profile, release, credential, account, position, or
order state.
