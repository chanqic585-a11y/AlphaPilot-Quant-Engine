# V13.4.10 Trend Pullback Redesign Review Summary

## Decision

- currentStatus: needs_redesign
- dryRunApproved: False
- recommendedNextStep: V13.4.11 - Execution Reality and Liquidity Gate Design
- The current Trend Pullback 1H V0.1 implementation is kept as research reference only.

## Smoke vs Expanded

| Scope | Trades | Return % | PF | Win Rate % | Max DD % | Max Loss Streak |
|---|---:|---:|---:|---:|---:|---:|
| V13.4.8 BTC/ETH/SOL smoke | 61 | 6.6227 | 1.1933 | 47.541 | 9.8727 | 5 |
| V13.4.9 Top30 raw | 472 | -61.0503 | 0.7067 | 31.5678 | 67.296 | 13 |
| V13.4.9 slippage-adjusted | 472 | -113.218 | 0.5361 | 30.7203 | 112.2244 | 13 |

The small positive smoke sample did not generalize to the wider Top30 six-month sample.

## Pair Concentration

- pairConcentrationAvailable: True
- supportedPairs: 28
- excludedPairs: TON/USDT:USDT, FET/USDT:USDT
- largestPairAbsContributionPct: 10.3842
- BTC/ETH/SOL adjusted total profit abs: -68.7442361
- Other pairs adjusted total profit abs: -1063.43621155

### Top Raw Profit Pairs

- ETH/USDT:USDT: 6.12%, trades=24, PF=1.7874
- SOL/USDT:USDT: 5.56%, trades=23, PF=1.6883
- TRX/USDT:USDT: 2.66%, trades=32, PF=1.3249
- LINK/USDT:USDT: 0.94%, trades=28, PF=1.0829
- UNI/USDT:USDT: 0.42%, trades=13, PF=1.0908

### Top Raw Loss Pairs

- BTC/USDT:USDT: -8.83%, trades=36, PF=0.4617
- FIL/USDT:USDT: -5.46%, trades=16, PF=0.3752
- ETC/USDT:USDT: -5.33%, trades=13, PF=0.2752
- AVAX/USDT:USDT: -4.78%, trades=22, PF=0.5768
- APT/USDT:USDT: -4.32%, trades=17, PF=0.4593

## Monthly / Regime Breakdown

- monthlyBreakdownAvailable: True
- Worst raw months:
  - 2026-01: -234.58263871 USDT, trades=101
  - 2026-04: -155.103966 USDT, trades=188
  - 2026-05: -152.76014082 USDT, trades=140
- Worst slippage-adjusted months:
  - 2026-01: -394.29915577 USDT, trades=101
  - 2026-04: -362.95121646 USDT, trades=188
  - 2026-05: -254.25440607 USDT, trades=140

## Cost Sensitivity

- tradeCount: 472
- rawTotalReturnPct: -61.0503
- slippageAdjustedTotalReturnPct: -113.218
- returnDegradationPctPoints: -52.1677
- rawProfitFactor: 0.7067
- slippageAdjustedProfitFactor: 0.5361
- profitFactorDegradation: -0.1706
- slippageCost: 521.67704423

## Payoff Review

- payoffDetailsAvailable: False
- configuredStopLoss: -2.5%
- configuredTakeProfit: +5%
- expandedRawWinRate: 31.5678
- expandedAdjustedWinRate: 30.7203
- The apparent 2:1 configured payoff did not survive expanded validation.
- The expanded win rate fell to roughly 31.6% raw and 30.7% after slippage adjustment.
- Average win/loss details are unavailable in the V13.4.9 report, so this review does not invent them.
- The likely issue is entry quality and path behavior: too many trades reach stop-loss or weak exits before +5%.

## Filter Review

Likely weak or incomplete areas:
- volumeRatio >= 1.2 may still admit noisy rebounds in weaker altcoins.
- BTC safety alone does not represent full market regime strength.
- Pullback and reclaim checks are binary and do not score trend quality.
- No-chase and ATR filters reduce obvious bad entries but do not ensure positive expectancy.
Missing filter categories:
- pair-level liquidity filter
- execution reality filter
- market regime filter beyond BTC only
- signal score / quality gate
- pair-specific trade cap or exposure cap

## Failure Findings

- V13.4.8 small BTC/ETH/SOL smoke profit did not generalize to Top30 six-month validation.
- V13.4.9 expanded raw result is deeply negative.
- Slippage-adjusted post-processing worsened the already failed result.
- The current strategy cannot enter Dry-run.
- Continuing to micro-tune the current rules has high overfitting risk.
- The next design must address pair selection, market regime, signal quality, and execution cost.

## Redesign Options

### Pair Universe Narrowing

- id: option_a_pair_universe_narrowing
- direction: Trade only high-liquidity majors or a high-quality subset instead of all Top30 pairs.
- evidence:
  - V13.4.8 BTC/ETH/SOL smoke was positive.
  - V13.4.9 Top30 expansion failed deeply.
  - BTC/ETH/SOL expanded adjusted total profit abs: -68.7442361
- risks:
  - smaller sample
  - overfitting to BTC/ETH/SOL
  - may miss broader market opportunities

### Market Regime Filter

- id: option_b_market_regime_filter
- direction: Enable Trend Pullback only during trend-friendly market regimes.
- evidence:
  - Expanded losses occurred across multiple months.
  - Single BTC safety was not enough to protect Top30 exposure.
- risks:
  - more data needed
  - fewer signals
  - more complex validation

### Signal Score / Quality Gate

- id: option_c_signal_score_quality_gate
- direction: Replace binary pass/fail entry with low-frequency high-quality signal scoring.
- evidence:
  - Current filters still generated 472 expanded trades with negative expectancy.
- risks:
  - subjective weights
  - possible overfitting
  - may create too few trades

### Liquidity / Execution Reality Filter

- id: option_d_liquidity_execution_reality_filter
- direction: Add pre-trade liquidity and execution feasibility checks.
- evidence:
  - Slippage-adjusted return degraded to -113.218%.
  - Slippage cost estimate: 521.67704423.
- risks:
  - requires more market data
  - first version may only approximate execution quality

### Alternate Strategy Direction

- id: option_e_alternate_strategy_direction
- direction: Pause Trend Pullback and return to Breakout Retest or another V03/V04 direction.
- evidence:
  - Trend Pullback failed expanded validation severely.
- risks:
  - longer development cycle
  - new strategy also requires full validation

## Do Not Proceed

- Do not enter Dry-run.
- Do not connect live trading.
- Do not add or store API keys.
- Do not auto trade.
- Do not continue scaling the current Top30 Trend Pullback rule set.
- Do not treat the V13.4.8 small-sample positive result as strategy approval.

## Safety

V13.4.10 reads local reports and writes research artifacts only. It does not modify strategy code, run backtests, download data, enter Dry-run, use API keys, call Trade API or Withdraw API, read accounts, create orders, or auto trade.
