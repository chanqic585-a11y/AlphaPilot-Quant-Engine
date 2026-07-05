# AlphaPilot V13.5.20 Exit-Aware Loss Cooldown

This report evaluates loss cooldown policies that only activate after a historical selected trade closes.

## Best Policy

- policyId: pair_loss_exit_21d
- description: After a selected trade closes at a loss, pause that pair for twenty-one days.
- tradeCount: 412
- winRatePct: 50.9709
- profitFactor: 1.873058
- rewardRiskRatio: 1.801704
- totalR: 167.6562
- maxDrawdownR: 13.0628
- maxConsecutiveLosses: 11
- gatePassed: True

## Policy Table

- pair_loss_exit_21d: trades=412, winRate=50.9709, pf=1.873058, rr=1.801704, maxDDR=13.0628, maxCL=11, passed=True
- pair_loss_exit_5d: trades=445, winRate=50.3371, pf=1.838458, rr=1.813836, maxDDR=15.3684, maxCL=12, passed=True
- global_loss_exit_pause_48h: trades=355, winRate=49.0141, pf=1.752027, rr=1.822511, maxDDR=14.3242, maxCL=12, passed=True
- global_loss_exit_pause_8h: trades=451, winRate=50.9978, pf=1.921389, rr=1.846204, maxDDR=15.7071, maxCL=14, passed=False
- pair_loss_exit_14d: trades=426, winRate=50.939, pf=1.862511, rr=1.793847, maxDDR=14.0396, maxCL=11, passed=False
- pair_loss_exit_3d: trades=450, winRate=50.4444, pf=1.848947, rr=1.816366, maxDDR=15.3684, maxCL=14, passed=False
- pair_loss_exit_10d: trades=430, winRate=50.4651, pf=1.82647, rr=1.792802, maxDDR=15.0163, maxCL=11, passed=False
- pair_loss_exit_7d: trades=436, winRate=50.0, pf=1.799418, rr=1.799418, maxDDR=15.0163, maxCL=12, passed=False
- global_loss_exit_pause_24h: trades=401, winRate=48.1297, pf=1.674562, rr=1.804709, maxDDR=16.2789, maxCL=14, passed=False

## Decision

- readyForLocalPaperRefreshReview: True
- readyForExchangeDryRunReview: False
- nextAction: prepare_local_paper_refresh_candidate

## No-Lookahead Rule

- Loss cooldown is triggered by `exitDate` only after the selected historical trade is closed.
- Entry rules and the 2R target are unchanged.

## Safety Boundary

- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No order creation.
- No automatic trading.
- No exchange Dry-run approval.
- No live-trading approval.
