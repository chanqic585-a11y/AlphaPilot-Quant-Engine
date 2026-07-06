# AlphaPilot V13.5.23 Alpha191 Crypto-Safe Subset Replay

This report implements a small Alpha191-inspired factor subset and evaluates it with existing local research gates.
It is concept-inspired only and does not copy Alpha191 formulas.

## Best Raw Candidate

- candidateId: 4h:a191_short_exhaustion_quality_v01:sl0.06:h24
- overlayId: a191_short_exhaustion_quality_v01
- trades: 3736
- winRatePct: 40.5514
- profitFactor: 1.163
- rewardRiskRatio: 1.705
- maxDrawdownPct: 99.7438
- rawGatePassed: False

## Exit-Aware Best Policy

- policyId: global_loss_exit_pause_8h
- trades: 1412
- profitFactor: 1.307052
- rewardRiskRatio: 1.688983
- maxDrawdownR: 91.7798
- gatePassed: False

## Local Paper Gate

- filledSignalCount: 1112
- winRatePct: 42.8957
- profitFactor: 1.3785
- rewardRiskRatio: 1.8351
- maxDrawdownPct: 51.845183
- gatePassed: False

## Top Candidates

- 4h:a191_short_exhaustion_quality_v01:sl0.06:h24: trades=3736, winRate=40.5514, pf=1.163, rr=1.705, dd=99.7438, rawGate=False
- 4h:a191_short_exhaustion_quality_v01:sl0.08:h30: trades=3736, winRate=43.3084, pf=1.1672, rr=1.5279, dd=99.9862, rawGate=False
- 4h:a191_short_residual_exhaustion_v01:sl0.06:h24: trades=6642, winRate=41.9603, pf=1.2043, rr=1.6658, dd=99.8879, rawGate=False
- 4h:a191_short_exhaustion_quality_v01:sl0.05:h18: trades=3736, winRate=40.2034, pf=1.1218, rr=1.6686, dd=99.1134, rawGate=False
- 4h:a191_short_residual_exhaustion_v01:sl0.08:h30: trades=6642, winRate=45.2273, pf=1.2727, rr=1.5413, dd=99.981, rawGate=False
- 4h:a191_short_residual_exhaustion_v01:sl0.05:h18: trades=6642, winRate=41.1623, pf=1.1334, rr=1.62, dd=99.8326, rawGate=False
- 4h:a191_short_exhaustion_quality_v01:sl0.04:h12: trades=3736, winRate=39.909, pf=1.0385, rr=1.5637, dd=99.891, rawGate=False
- 4h:a191_short_residual_exhaustion_v01:sl0.04:h12: trades=6642, winRate=40.9967, pf=1.0669, rr=1.5354, dd=99.9398, rawGate=False
- 4h:a191_short_range_rejection_v01:sl0.06:h24: trades=6899, winRate=41.3393, pf=1.0893, rr=1.5458, dd=99.9788, rawGate=False
- 4h:a191_short_range_rejection_v01:sl0.05:h18: trades=6899, winRate=40.2087, pf=1.0559, rr=1.5702, dd=99.9127, rawGate=False
- 4h:a191_short_range_rejection_v01:sl0.08:h30: trades=6899, winRate=43.557, pf=1.121, rr=1.4526, dd=99.9993, rawGate=False
- 4h:a191_short_range_rejection_v01:sl0.04:h12: trades=6899, winRate=40.2377, pf=1.0046, rr=1.492, dd=99.9963, rawGate=False

## Decision

- alpha191SubsetImplemented: True
- rawReplayGatePassed: False
- exitAwareGatePassed: False
- localPaperGatePassed: False
- readyForForwardRefreshComparison: False
- exchangeDryRunApproved: False
- liveTradingApproved: False
- nextAction: keep_alpha191_subset_as_research_only_and_do_not_replace_v13_5_21

## Safety Boundary

- Research replay only.
- No Alpha191 full formula copying.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No order creation.
- No automatic trading.
- No exchange Dry-run approval.
- No live-trading approval.
