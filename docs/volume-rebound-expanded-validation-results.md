# Volume Rebound Expanded Validation Results

This document records the V13.4.5 expanded validation result for AlphaPilot Volume Rebound candidates.

## Scope

```text
Timerange: 20260101-
Requested pairs: fixed Top30
Supported pairs: 28
Excluded pairs: TON/USDT:USDT, FET/USDT:USDT
Strategies: V01, V02B, V02C, V02E
Slippage: 0.05% one-way post-processing
```

## Raw Comparison

| Strategy | Return % | Max DD % | Profit Factor | Trades | Win Rate % | Max Loss Streak |
|---|---:|---:|---:|---:|---:|---:|
| V01 baseline | -99.2732 | 99.3724 | 0.6689 | 2701 | 37.2825 | 28 |
| V02B Volume Quality | -94.1710 | 94.7185 | 0.6152 | 1515 | 36.9637 | 19 |
| V02C Exit Cleanup | -99.1303 | 99.2719 | 0.6739 | 2496 | 43.4295 | 25 |
| V02E Pair Risk Watchlist | -99.3093 | 99.3953 | 0.6637 | 2671 | 37.0273 | 20 |

## Slippage-Adjusted Comparison

| Strategy | Adj Return % | Adj DD % | Adj PF | Trades | Adj Win Rate % | Max Loss Streak | Slippage Cost | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| V01 baseline | -193.4577 | 191.6168 | 0.4603 | 2701 | 34.6909 | 28 | 941.84466739 | false |
| V02B Volume Quality | -168.5489 | 165.9553 | 0.4225 | 1515 | 34.7195 | 36 | 743.77896729 | false |
| V02C Exit Cleanup | -187.2377 | 182.3083 | 0.4726 | 2496 | 39.7436 | 25 | 881.07407065 | true |
| V02E Pair Risk Watchlist | -191.7425 | 190.0944 | 0.4569 | 2671 | 34.4066 | 20 | 924.33185017 | false |

## Interpretation

V02C is the best relative candidate by profit factor and is the only candidate that passes the expanded research gate. This does not make it usable for Dry-run. Its slippage-adjusted total return remains deeply negative.

V02B reduced trade count and raw drawdown, but it failed the expanded gate after slippage because its adjusted profit factor was weaker and max consecutive losses worsened.

V02E did not provide enough improvement over the baseline after slippage.

## Decision

```text
dryRunApproved = false
```

No candidate is ready for Dry-run or live trading. The next step should be V13.4.6 strategy direction review / V03 redesign, with special attention to:

- reducing trade frequency,
- improving entry selectivity,
- avoiding fee and slippage drag,
- rethinking the payoff structure,
- validating on longer timeranges only after the strategy logic is redesigned.

## V13.4.6 Follow-up

V13.4.6 formally rejects the current V0.1/V0.2 series for Dry-run and archives
the family as failed research for the current sample.

The direction after this report is not more B/C/E micro-tuning. The next
research step is V03 strategy redesign, with a new entry-quality framework,
lower trade frequency, stronger reward/risk requirements, pair-level exposure
controls, and slippage-adjusted quality gates.

## Safety

This result is historical research only. It does not use real API keys, does not call Trade API or Withdraw API, does not read real accounts or positions, does not create orders, and does not auto trade.
