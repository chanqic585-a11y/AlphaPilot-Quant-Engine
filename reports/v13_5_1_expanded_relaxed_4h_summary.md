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

- Trade count: `39`
- Win rate: `64.1026`
- Reward/risk: `0.9307`
- Profit factor: `1.662`
- Total return: `43.7149`
- Max drawdown: `22.4666`
- Hard gate passed: `False`
- Relaxed gate passed: `False`
- Observation gate passed: `False`

## Best Deterministic Mined Candidate

- Columns: `bucket_btc_regime, bucket_return_3, bucket_bollinger_z`
- Values: `bear, > 0.06, > 2.0`
- Trade count: `166`
- Win rate: `60.8434`
- Reward/risk: `1.9922`
- Profit factor: `3.0956`
- Max drawdown: `35.4801`
- Hard gate passed: `False`
- Relaxed gate passed: `False`
- Holdout metrics: `{'tradeCount': 50, 'winRatePct': 56.0, 'averageWinPct': 9.749606, 'averageLossPct': -4.883247, 'rewardRiskRatio': 1.9965, 'profitFactor': 2.5411, 'totalReturnPct': 338.2686, 'maxDrawdownPct': 35.4801, 'researchWorthContinuing': False}`

## Search

- Config count: `45`
- Hard passing configs: `0`
- Relaxed passing configs: `0`
- Observation passing configs: `0`
- Deterministic holdout relaxed passing count: `0`
- Deterministic full-sample relaxed count: `200`

## Data

- Panel rows: `43578`
- Loaded pairs: `28`
- Missing pairs: `none`
- Open interest status: `unavailable_not_fabricated`

## Recommendations

- A deterministic mined candidate exists, but probability-gated configs did not pass.
- Treat this as a forward-confirmation candidate only; it may be data-mined.
- Best mined full-sample metrics: trades=166, winRate=60.8434, rewardRisk=1.9922, profitFactor=3.0956, maxDrawdown=35.4801.
- Best mined holdout metrics: trades=50, winRate=56.0, rewardRisk=1.9965, profitFactor=2.5411, maxDrawdown=35.4801.
- Do not start paper, Dry-run, or live trading until a probability-gated walk-forward candidate confirms it.
