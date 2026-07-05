# V13.5.1 Expanded Relaxed Derivatives Research Report

This report is research-only. Relaxed candidates are shadow-watchlist candidates, not trading approval.

## Decision

- Probability hard gate approved: `False`
- Probability relaxed shadow-watchlist approved: `False`
- Deterministic forward-confirmation candidate found: `True`
- Deterministic holdout relaxed candidate found: `False`
- Paper approved: `False`
- Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `deterministic_forward_confirmation_candidate_found`

## Best Probability-Gated Candidate

- Trade count: `2963`
- Win rate: `49.6456`
- Reward/risk: `1.1373`
- Profit factor: `1.1213`
- Total return: `2880.3423`
- Max drawdown: `99.9538`
- Hard gate passed: `False`
- Relaxed gate passed: `False`
- Observation gate passed: `False`

## Best Deterministic Mined Candidate

- Columns: `bucket_setupName, bucket_btc_regime, bucket_relative_return_6`
- Values: `short_reversal_candidate, bull, (-0.01, 0.01]`
- Trade count: `187`
- Win rate: `73.262`
- Reward/risk: `1.2321`
- Profit factor: `3.3759`
- Max drawdown: `37.9023`
- Hard gate passed: `False`
- Relaxed gate passed: `False`
- Holdout metrics: `{'tradeCount': 57, 'winRatePct': 70.1754, 'averageWinPct': 4.948516, 'averageLossPct': -2.445492, 'rewardRiskRatio': 2.0235, 'profitFactor': 4.7612, 'totalReturnPct': 346.661, 'maxDrawdownPct': 11.9756, 'researchWorthContinuing': False}`

## Search

- Config count: `80`
- Hard passing configs: `0`
- Relaxed passing configs: `0`
- Observation passing configs: `0`
- Deterministic holdout relaxed passing count: `0`
- Deterministic full-sample relaxed count: `362`

## Data

- Panel rows: `123542`
- Loaded pairs: `28`
- Missing pairs: `none`
- Open interest status: `unavailable_not_fabricated`

## Recommendations

- A deterministic mined candidate exists, but probability-gated configs did not pass.
- Treat this as a forward-confirmation candidate only; it may be data-mined.
- Best mined full-sample metrics: trades=187, winRate=73.262, rewardRisk=1.2321, profitFactor=3.3759, maxDrawdown=37.9023.
- Best mined holdout metrics: trades=57, winRate=70.1754, rewardRisk=2.0235, profitFactor=4.7612, maxDrawdown=11.9756.
- Do not start paper, Dry-run, or live trading until a probability-gated walk-forward candidate confirms it.
