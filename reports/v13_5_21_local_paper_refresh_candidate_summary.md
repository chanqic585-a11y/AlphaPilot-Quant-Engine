# AlphaPilot V13.5.21 Local Paper Refresh Candidate

This report packages V13.5.20 selected signals into the local paper sandbox ledger.
It is local simulation only and does not create exchange orders.

## Candidate

- candidateId: 4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24
- selectedPolicyId: pair_loss_exit_21d
- stopLossPct: 0.06
- targetRMultiple: 2.0
- maxConcurrentPositions: 8

## Ledger Metrics

- filledSignalCount: 409
- skippedSignalCount: 3
- winRatePct: 51.1002
- profitFactor: 1.9588
- rewardRiskRatio: 1.8744
- totalReturnPct: 378.8964
- maxDrawdownPct: 11.841614
- finalEquity: 47889.640696

## Concurrency Sensitivity

- cap=3: filled=348, skipped=64, pf=1.7996, rr=1.8204, dd=15.190288, passed=False
- cap=5: filled=392, skipped=20, pf=1.8446, rr=1.8073, dd=11.403698, passed=True
- cap=8: filled=409, skipped=3, pf=1.9588, rr=1.8744, dd=11.841614, passed=True
- cap=12: filled=412, skipped=0, pf=1.9672, rr=1.8923, dd=13.39029, passed=True
- cap=999: filled=412, skipped=0, pf=1.9672, rr=1.8923, dd=13.39029, passed=True

## Decision

- localPaperRefreshCandidateReady: True
- localPaperMechanicsPassed: True
- readyForExchangeDryRunReview: False
- nextAction: run_forward_readiness_when_new_closed_samples_are_available

## Safety Boundary

- Local simulated capital only.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No order creation.
- No automatic trading.
- No exchange Dry-run approval.
- No live-trading approval.
