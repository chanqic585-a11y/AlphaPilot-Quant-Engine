# V13.4.3 V0.2 Candidate Summary

## Current V0.1 Conclusion

V0.1 is not approved for Dry-run or live trading.

Baseline evidence:

- Total return: -15.542
- Max drawdown: 24.4939
- Profit factor: 0.8107
- Max consecutive losses: 13
- Final entries / actual trades: 305 / 230

## Why Dry-run Is Blocked

- V13.4 smoke backtest is negative.
- Profit factor is below 1.
- Drawdown and loss streak are too high for a controlled execution path.
- V13.4.3 only creates candidate designs for V13.4.4 comparison.

## Evidence Summary

- Top skip reason: {'skipReason': 'weak_4h_trend', 'count': 11926, 'percentage': 45.0106}
- SOL pair evidence: {'pair': 'SOL/USDT:USDT', 'totalProfit': -94.83085485, 'profitFactor': 0.7643, 'tradeCount': 99}
- SOL signal/trade count: {'finalEntryCount': 135, 'actualTradeCount': 99}
- Stop-loss net profit: -420.36251129
- MACD weakness exit net profit: -345.28583144
- Weakest holding bucket: {'bucket': '1-3h', 'netProfit': -120.76496941, 'tradeCount': 117}
- Estimated fees paid: 339.82529451
- Slippage applied in V13.4: False

## Candidate Matrix

### V0.2A Trend Strict Filter

Strengthen the 4h trend gate to reduce weak-trend rebound failures.

Proposed changes:

- Compare close_4h >= ema200_4h instead of close_4h >= ema200_4h * 0.98.
- Optionally require 4h EMA20 >= 4h EMA200.
- Optionally require non-negative 4h EMA20 slope.

Expected impact:

- Reduce trades in weak trend regimes.
- Reduce stop-loss pressure from low-quality rebounds.
- Lower total trade count before fees.

Risks:

- May filter too aggressively and miss early rebounds.
- May reduce sample size enough to make results unstable.
- Could overfit the V13.4 smoke period if adopted without broader comparison.

What to test:

- V0.1 baseline versus trend-strict variant on the same BTC/ETH/SOL smoke sample.
- Compare total return, max drawdown, profit factor, trade count, and max consecutive losses.
- Review pair and month breakdown to ensure April loss does not simply move to another bucket.

### V0.2B Volume Quality Filter

Raise the volume-quality bar to reduce low-quality rebound attempts and fee drag.

Proposed changes:

- Compare volumeRatio >= 2.0 against the V0.1 threshold of 1.5.
- Add a non-isolated spike check so one-candle volume spikes do not qualify alone.
- Consider a candle body quality check before accepting a rebound candle.

Expected impact:

- Reduce low-quality trades.
- Reduce fee drag by lowering unnecessary entries.
- Potentially improve signal selectivity.

Risks:

- May reject valid early rebounds.
- Volume thresholds can be pair-specific and unstable across regimes.
- A stricter threshold may reduce trades without improving expectancy.

What to test:

- Compare trade count reduction versus profit factor improvement.
- Review whether SOL remains overrepresented after volume-quality filtering.
- Run fee and slippage-adjusted metrics in V13.4.4.

### V0.2C Exit Cleanup

Re-evaluate MACD weakness exit behavior because it lost heavily in V13.4.1.

Proposed changes:

- Compare MACD weakness exit only when current trade profit is positive.
- Compare removing MACD weakness exit and relying on ROI, stoploss, and time stop.
- Compare MACD weakness exit only when close is also below EMA20.

Expected impact:

- Reduce noisy exits that cut positions in losing zones.
- Clarify whether MACD exit helps or hurts net expectancy.
- Potentially improve average loss handling if combined with early failure logic.

Risks:

- Removing or gating MACD exit may hold losing trades longer.
- May increase drawdown or stop-loss count.
- Exit changes can interact with ROI and time stop in non-obvious ways.

What to test:

- Compare exit-reason breakdown after each exit-cleanup variant.
- Track stop_loss loss and MACD weakness loss separately.
- Require drawdown and max-loss-streak checks before considering any exit variant.

### V0.2D Early Failure Exit

Add an early failure check for rebounds that do not work soon after entry.

Proposed changes:

- Compare an exit if the trade is not profitable after 4 closed 15m candles.
- Compare an exit if the trade is not profitable after 6 closed 15m candles.
- Compare replacing 12-candle no-profit time stop with 8 closed 15m candles.

Expected impact:

- Reduce failed rebounds before they reach stop loss.
- Reduce time spent in unproductive 1-3h trades.
- Potentially reduce max consecutive losses.

Risks:

- May exit before delayed rebounds recover.
- May reduce win rate if early failure rules are too sensitive.
- Needs careful slippage/fee treatment because it can add churn.

What to test:

- Compare 4-candle, 6-candle, and 8-candle variants separately.
- Measure changes in 1-3h holding bucket, stop_loss loss, and total fees.
- Reject variants that improve return but worsen drawdown materially.

### V0.2E Pair Risk Watchlist

Track pair-level risk and exposure without permanently excluding SOL.

Proposed changes:

- Add pair-level monitoring to the comparison report.
- Compare pair-level cooldown after a loss streak.
- Compare max trades per pair per day.
- Compare pair-level risk cap without permanently excluding SOL.

Expected impact:

- Reduce single-pair overexposure.
- Make pair-specific drawdown visible before Top 30 expansion.
- Prepare a risk-control layer for broader universes.

Risks:

- The smoke sample is too small to permanently blacklist a pair.
- Pair caps may reduce opportunity without improving expectancy.
- Pair-level controls can overfit recent volatility.

What to test:

- Measure pair contribution before and after pair-level controls.
- Compare SOL-specific loss reduction against total return and opportunity cost.
- Require the same logic to be tested on BTC and ETH, not SOL only.

## V13.4.4 Comparison Plan

- Step 1: V0.1 baseline - Keep the current V13.4 smoke baseline unchanged for comparison.
- Step 2: V0.2A trend strict - Test whether stricter 4h trend context reduces weak-trend losses.
- Step 3: V0.2B volume quality - Test whether a stronger volume-quality gate reduces fee drag and weak signals.
- Step 4: V0.2C exit cleanup - Test MACD weakness exit gating or removal against stop-loss and drawdown effects.
- Step 5: V0.2D early failure exit - Test whether earlier failure exits improve 1-3h loss behavior.
- Step 6: V0.2E pair risk watchlist - Test pair-level risk controls without permanently removing any pair.

Comparison must include return, drawdown, profit factor, trade count, win rate, loss streak, pair/month performance, exit reason losses, fees, and slippage-adjusted net return.

## Do Not Change Yet

- Do not enter Dry-run immediately.
- Do not trade live.
- Do not permanently remove SOL.
- Do not directly change stoploss.
- Do not directly change take profit.
- Do not raise volumeRatio and treat it as final without comparison.
- Do not remove MACD weakness exit and ship it without comparison.
- Do not overfit to one smoke timerange.
- Do not expand to Top 30 before V0.2 comparison evidence is reviewed.

## Safety

V13.4.3 does not modify V0.1 strategy logic, change config defaults, run Dry-run, call Trade API or Withdraw API, save API keys, read accounts, create orders, or auto trade.
