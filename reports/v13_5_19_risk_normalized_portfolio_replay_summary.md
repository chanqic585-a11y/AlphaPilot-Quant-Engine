# AlphaPilot V13.5.19 Risk-Normalized Portfolio Replay

This report applies fixed portfolio-level throttles to the V13.5.18 historical signal log in R-multiple space.

## Best Policy

- policyId: pair_14d_cooldown
- description: At most one selected signal per pair every fourteen days.
- tradeCount: 264
- winRatePct: 46.9697
- profitFactor: 1.565222
- rewardRiskRatio: 1.767186
- totalR: 74.8552
- maxDrawdownR: 7.4706
- maxConsecutiveLosses: 7
- gatePassed: False

## Policy Table

- pair_14d_cooldown: trades=264, pf=1.565222, rr=1.767186, maxDDR=7.4706, passed=False
- loss_guard_pair_21d: trades=262, pf=1.590823, rr=1.770432, maxDDR=8.4474, passed=False
- exchange_24h_pair_7d: trades=252, pf=1.52, rr=1.782069, maxDDR=7.2519, passed=False
- pair_7d_cooldown: trades=275, pf=1.549019, rr=1.778951, maxDDR=8.4474, passed=False
- drawdown_guard_12r_pause_14d: trades=275, pf=1.549019, rr=1.778951, maxDDR=8.4474, passed=False
- global_24h_pair_14d: trades=219, pf=1.505204, rr=1.758555, maxDDR=7.2519, passed=False
- exchange_24h_pair_14d: trades=243, pf=1.495204, rr=1.748855, maxDDR=7.2519, passed=False
- raw_all_signals: trades=500, pf=1.777458, rr=1.820635, maxDDR=19.614, passed=False

## Decision

- readyForLocalPaperRefreshReview: False
- readyForExchangeDryRunReview: False
- nextAction: tighten_risk_controls_or_wait_for_forward_readiness

## Safety Boundary

- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No order creation.
- No automatic trading.
