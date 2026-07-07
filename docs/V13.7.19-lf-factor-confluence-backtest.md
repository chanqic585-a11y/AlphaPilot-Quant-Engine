# AlphaPilot V13.7.19 LF Factor Confluence Backtest

This is a deterministic research backtest for `lf_factor_confluence_regime_filter_4h_v0_1`.
It is not exchange Dry-run, not live trading, not an order, and not trading advice.

## Summary

- status: completed
- experimentId: lf_factor_confluence_regime_filter_4h_v0_1
- strategyName: LF Factor Confluence Regime Filter 4H V0.1
- timerange: 20200101-
- timeframe: 4h
- pairCount: 38
- tradeCount: 92
- winRatePct: 39.1304
- profitFactor: 1.1694
- targetRewardRiskRatio: 2.0
- realizedRewardRiskRatio: 1.8191
- totalReturnPct: 9.7877
- maxDrawdownPct: 18.8774
- maxConsecutiveLosses: 8
- passGatePassed: False
- paperObservationApproved: False
- exchangeDryRunApproved: False
- liveTradingApproved: False

## Gate Checks

- minTradeCount: True
- minRewardRiskRatio: True
- minProfitFactor: True
- maxDrawdownPct: True
- mustBeatNoTrade: True
- mustBeatEqualWeight: True
- walkForwardValidationPositive: False
- walkForwardTestPositive: True

## Baseline Comparison

- beatsNoTrade: True
- beatsEqualWeight: True
- equalWeightReturnPct: 2.5054
- strategyReturnPct: 9.7877
- equalWeightMaxDrawdownPct: 62.9563
- strategyMaxDrawdownPct: 18.8774

## Walk Forward

| splitId | Trades | Win % | PF | Return % | Max DD % | Total R | Max Losses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| train_2020_2022 | 19 | 52.6316 | 1.9588 | 9.0119 | 3.8413 | 9.0119 | 3 |
| validation_2023_2024 | 49 | 28.5714 | 0.7358 | -9.7241 | 19.3462 | -9.7241 | 8 |
| test_2025_2026 | 24 | 50.0 | 1.9075 | 10.4999 | 3.7127 | 10.4999 | 4 |

## Pair Breakdown

| pair | Trades | Win % | PF | Return % | Max DD % | Total R | Max Losses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AAVE/USDT:USDT | 4 | 25.0 | 0.9054 | -0.205 | 1.1165 | -0.205 | 2 |
| ADA/USDT:USDT | 6 | 33.3333 | 0.9362 | -0.2651 | 2.0297 | -0.2651 | 2 |
| APT/USDT:USDT | 1 | 0.0 | 0.0 | -1.0491 | 0.0 | -1.0491 | 1 |
| ATOM/USDT:USDT | 1 | 0.0 | 0.0 | -1.0459 | 0.0 | -1.0459 | 1 |
| AVAX/USDT:USDT | 4 | 50.0 | 1.8814 | 1.8329 | 2.0392 | 1.8329 | 2 |
| BCH/USDT:USDT | 5 | 40.0 | 1.2661 | 0.8228 | 1.0359 | 0.8228 | 2 |
| BNB/USDT:USDT | 3 | 0.0 | 0.0 | -3.2024 | 2.1652 | -3.2024 | 3 |
| CFX/USDT:USDT | 1 | 0.0 | 0.0 | -1.0157 | 0.0 | -1.0157 | 1 |
| CRV/USDT:USDT | 4 | 50.0 | 1.9076 | 1.8627 | 1.975 | 1.8627 | 2 |
| DOGE/USDT:USDT | 5 | 40.0 | 1.2447 | 0.7727 | 1.0714 | 0.7727 | 1 |
| DOT/USDT:USDT | 1 | 0.0 | 0.0 | -1.0298 | 0.0 | -1.0298 | 1 |
| DYDX/USDT:USDT | 4 | 25.0 | 0.6281 | -1.1484 | 1.0416 | -1.1484 | 2 |
| ETC/USDT:USDT | 1 | 0.0 | 0.0 | -1.0304 | 0.0 | -1.0304 | 1 |
| ETH/USDT:USDT | 4 | 50.0 | 1.8267 | 1.7672 | 2.0574 | 1.7672 | 2 |
| FIL/USDT:USDT | 1 | 0.0 | 0.0 | -1.0406 | 0.0 | -1.0406 | 1 |
| FLOW/USDT:USDT | 1 | 100.0 | None | 1.94 | 0.0 | 1.94 | 0 |
| GRT/USDT:USDT | 2 | 100.0 | None | 3.9402 | 0.0 | 3.9402 | 0 |
| INJ/USDT:USDT | 1 | 100.0 | None | 1.9555 | 0.0 | 1.9555 | 0 |
| KSM/USDT:USDT | 4 | 25.0 | 0.6173 | -1.2053 | 2.1113 | -1.2053 | 3 |
| LINK/USDT:USDT | 4 | 50.0 | 1.864 | 1.8008 | 2.0447 | 1.8008 | 2 |
| LTC/USDT:USDT | 3 | 66.6667 | 3.7115 | 2.8534 | 1.0128 | 2.8534 | 1 |
| NEAR/USDT:USDT | 2 | 50.0 | 1.8877 | 0.9281 | 1.0253 | 0.9281 | 1 |
| OP/USDT:USDT | 1 | 0.0 | 0.0 | -1.0353 | 0.0 | -1.0353 | 1 |
| ORDI/USDT:USDT | 1 | 0.0 | 0.0 | -1.0247 | 0.0 | -1.0247 | 1 |
| PEPE/USDT:USDT | 1 | 0.0 | 0.0 | -1.0183 | 0.0 | -1.0183 | 1 |
| SHIB/USDT:USDT | 3 | 33.3333 | 0.3564 | -1.3584 | 1.0716 | -1.3584 | 2 |
| SOL/USDT:USDT | 3 | 66.6667 | 3.6356 | 2.8035 | 0.0 | 2.8035 | 1 |
| TIA/USDT:USDT | 1 | 0.0 | 0.0 | -1.0341 | 0.0 | -1.0341 | 1 |
| TRX/USDT:USDT | 14 | 64.2857 | 2.9038 | 10.5084 | 4.2856 | 10.5084 | 4 |
| UNI/USDT:USDT | 3 | 0.0 | 0.0 | -3.147 | 2.129 | -3.147 | 3 |

## Regime Breakdown

| btcPrimaryRegime | Trades | Win % | PF | Return % | Max DD % | Total R | Max Losses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| sideways | 92 | 39.1304 | 1.1694 | 9.7877 | 18.8774 | 9.7877 | 8 |

## Exit Reason Breakdown

| exitReason | Trades | Win % | PF | Return % | Max DD % | Total R | Max Losses |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| stop_loss | 55 | 0.0 | 0.0 | -57.6741 | 57.2265 | -57.6741 | 55 |
| target_2r | 34 | 100.0 | None | 65.9922 | 0.0 | 65.9922 | 0 |
| time_stop | 3 | 66.6667 | 16.3478 | 1.4697 | 0.0943 | 1.4697 | 1 |

## BTC Regime Source

- source: local_public_btc_4h_ohlcv_inline_proxy_v13_7_19
- labelCount: 14266
- firstTimestamp: 2020-01-01T00:00:00+00:00
- lastTimestamp: 2026-07-05T12:00:00+00:00
- note: Regime labels are computed deterministically from local BTC public OHLCV for full timerange coverage; no missing labels are fabricated.

## Safety Boundary

- realTradingEnabled: False
- exchangeDryRunApproved: False
- liveTradingApproved: False
- tradeApiEnabled: False
- withdrawApiEnabled: False
- apiKeyStorage: False
- realAccountReads: False
- realPositionReads: False
- orderCreation: False
- autoTrading: False

## Next Step

Keep this candidate in research. Adjust the rule only with new evidence; do not weaken the 2R target.
