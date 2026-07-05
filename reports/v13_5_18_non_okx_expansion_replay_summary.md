# AlphaPilot V13.5.18 Non-OKX Expansion Replay

This report reruns the fixed active pool after expanding Binance and Bybit public 4h data to Top20 candidates.

## Data Expansion

- okx: availablePairCount=38, targetPairCount=None, targetReached=None
- binance: availablePairCount=20, targetPairCount=20, targetReached=True
- bybit: availablePairCount=20, targetPairCount=20, targetReached=True

## Combined Active Pool Metrics

- tradeCount: 611
- winRatePct: 45.0082
- profitFactor: 1.5185
- rewardRiskRatio: 1.8553
- maxDrawdownPct: 89.731

## By Exchange

- okx: trades=309, winRate=51.1327, pf=1.9109, maxDD=54.9741
- binance: trades=196, winRate=36.2245, pf=1.1079, maxDD=89.731
- bybit: trades=106, winRate=43.3962, pf=1.3916, maxDD=71.9456

## Decision

- sampleAdequate: True
- exchangeBalanceAdequate: True
- readyForExchangeDryRunReview: False
- nextAction: review_drawdown_and_exchange_balance_before_any_forward_local_paper_refresh

## Safety Boundary

- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No order creation.
- No automatic trading.
