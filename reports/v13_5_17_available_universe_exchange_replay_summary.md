# AlphaPilot V13.5.17 Available-Universe Exchange Replay

This report expands the fixed active-pool replay to all locally available public 4h futures files per exchange.

## Combined Active Pool Metrics

- tradeCount: 313
- winRatePct: 51.1182
- profitFactor: 1.916
- rewardRiskRatio: 1.8322
- maxDrawdownPct: 54.9741

## By Exchange

- okx: pairs=38 / 38, panelRows=359791, activeTrades=309, winRate=51.1327, pf=1.9109
- binance: pairs=3 / 3, panelRows=41258, activeTrades=0, winRate=None, pf=None
- bybit: pairs=3 / 3, panelRows=35743, activeTrades=4, winRate=50.0, pf=2.2927

## Decision

- availableUniverseReplayCompleted: True
- sampleAdequate: True
- exchangeBalanceAdequate: False
- readyForExchangeDryRunReview: False
- nextAction: download_resumable_non_okx_universe_or_wait_for_forward_readiness

## Safety Boundary

- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No order creation.
- No automatic trading.
