# AlphaPilot V13.5.16 Core Multi-Exchange Replay

This report replays the fixed active research pool on local public BTC/ETH/SOL data across OKX, Binance, and Bybit.

## Active Pool

- poolId: 4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24
- timeframe: 4h
- stopLossPct: 0.06
- rewardRMultiple: 2.0
- horizonBars: 24

## Combined Active Pool Metrics

- tradeCount: 9
- winRatePct: 44.4444
- profitFactor: 1.8342
- rewardRiskRatio: 2.2927

## By Exchange

- okx: status=completed, panelRows=40475, loadedPairs=3, activeTrades=5, winRate=40.0, pf=1.5285
- binance: status=completed, panelRows=41258, loadedPairs=3, activeTrades=0, winRate=None, pf=None
- bybit: status=completed, panelRows=35743, loadedPairs=3, activeTrades=4, winRate=50.0, pf=2.2927

## Decision

- exchangeAwareCoreReplayCompleted: True
- activePoolCrossExchangeSampleAdequate: False
- readyForExchangeDryRunReview: False
- nextAction: expand_exchange_aware_replay_to_larger_resumable_universe_or_forward_ready_refresh

## Safety Boundary

- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No order creation.
- No automatic trading.
