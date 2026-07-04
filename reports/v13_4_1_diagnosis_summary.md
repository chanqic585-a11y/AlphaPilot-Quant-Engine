# V13.4.1 Backtest Result Diagnosis Summary

## Conclusion

V13.4 pipeline passed, but AlphaPilot Volume Rebound V0.1 must not enter Dry-run.

## Overall Metrics

- Total trades: 230
- Win rate: 41.3043%
- Total return: -15.542%
- Max drawdown: 24.4939%
- Profit factor: 0.8107
- Max consecutive losses: 13

## Main Loss Sources

- Worst pair: SOL/USDT:USDT (-94.83085485 USDT, -9.48%)
- Worst exit reason: stop_loss (-420.36251129 USDT)
- Weakest holding bucket: 1-3h (-120.76496941 USDT)

## Filter Effectiveness

Filter effectiveness is unavailable because V13.4 did not include skipped-signal instrumentation.

## V0.2 Candidate Ideas

- needs_more_backtest: Diagnose and possibly strengthen the 4h trend filter.
- hypothesis_only: Evaluate a higher volumeRatio threshold or a scored volume confirmation.
- needs_more_backtest: Add a stronger no-chase filter after sharp candles.
- data_supported: Review MACD weakness exit timing against actual loss distribution.
- data_supported: Analyze whether -3% stoploss and +3% ROI produce poor payoff at current win rate.
- data_supported: Add signal audit instrumentation before parameter tuning.

## Do Not Change Yet

- Do not modify stoploss yet.
- Do not modify take profit yet.
- Do not modify RSI range yet.
- Do not modify volumeRatio threshold yet.
- Do not modify BTC crash filter yet.
- Do not enter Dry-run.
- Do not expand to Top30 full backtest before diagnosis is reviewed.

## Safety

This diagnosis reads local backtest artifacts only. It does not use API keys, does not call Trade API or Withdraw API, does not read a real account, does not create orders, and does not auto trade.
