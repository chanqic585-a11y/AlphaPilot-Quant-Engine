# V13.5.3 Local Paper Sandbox Ledger Report

This report is local simulation only. It does not run exchange Dry-run, use API keys, read accounts, create orders, or auto trade.

## Decision

- Local paper sandbox started: `True`
- Paper monitoring ready: `True`
- Exchange Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `local_paper_sandbox_ledger_ready`
- Fail reasons: `none`

## Ledger Metrics

- Initial equity: `10000.0`
- Final equity: `11497.878914`
- Total return: `14.9788`
- Max drawdown: `3.242758`
- Filled trades: `41`
- Skipped signals: `66`
- Win rate: `60.9756`
- Reward/risk: `1.6922`
- Profit factor: `2.644`
- Max concurrent positions: `8`

## Concurrency Sensitivity

- Max positions `3`: ready=`False`, trades=`25`, return=`7.5038`, drawdown=`2.002764`, winRate=`68.0`, reward/risk=`1.0638`, PF=`2.2605`
- Max positions `5`: ready=`False`, trades=`33`, return=`9.0842`, drawdown=`3.242758`, winRate=`60.6061`, reward/risk=`1.3779`, PF=`2.1198`
- Max positions `8`: ready=`True`, trades=`41`, return=`14.9788`, drawdown=`3.242758`, winRate=`60.9756`, reward/risk=`1.6922`, PF=`2.644`
- Max positions `12`: ready=`True`, trades=`47`, return=`22.5306`, drawdown=`3.242758`, winRate=`63.8298`, reward/risk=`1.7582`, PF=`3.1026`
- Max positions `999`: ready=`True`, trades=`57`, return=`36.0394`, drawdown=`3.242758`, winRate=`70.1754`, reward/risk=`1.7428`, PF=`4.1008`

## Approved Candidates

- `v13_5_1_1h_short_reversal_bull_relative_return`

## Outputs

- Ledger: `reports\v13_5_3_local_paper_sandbox_ledger.json`

## Safety Boundary

- Local simulated capital only.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No real orders.
- No automatic trading.
- Exchange Dry-run remains disabled.
