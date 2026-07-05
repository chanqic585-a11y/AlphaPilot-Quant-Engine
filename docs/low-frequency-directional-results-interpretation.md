# Low-Frequency Directional Results Interpretation

V13.4.34 produced a completed real backtest and a failed research result.

## Result Files

```text
reports/v13_4_34_low_frequency_directional_4h_report.json
reports/v13_4_34_low_frequency_directional_4h_summary.md
user_data/backtest_results/v13_4_34_low_frequency_directional_4h.zip
```

## Key Findings

- The real backtest is not a mock result.
- Trade count is high for a low-frequency strategy.
- Both long and short sides lose money.
- Max drawdown is close to 100%.
- Post-processing slippage stress makes the result worse.
- The strategy does not beat NoTrade.
- The strategy does not beat EqualWeight BTC/ETH/SOL.

## Research Decision

`researchWorthContinuing` is false for this exact rule set.

This does not mean low-frequency research should stop. It means this specific score-gate implementation is not a viable candidate in its current form.

## Recommended Next Direction

Future low-frequency work should:

- reduce trade frequency
- require stronger regime agreement
- separate long and short candidates instead of combining them
- add stronger NoTrade defensive states
- compare every result against NoTrade, BuyHold, and EqualWeight baselines
- keep slippage stress in the report layer

## Safety Boundary

These results are historical research records only. They are not trading advice, not a signal, not a Dry-run approval, and not a live trading approval.

