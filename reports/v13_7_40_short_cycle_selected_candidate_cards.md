# V13.7.40 Short-Cycle Selected Candidate Cards

These are research-only candidates selected from public Binance Vision OHLCV. They are not exchange dry-run, live trading, orders, or trading advice.

All candidates keep a fixed 2R target. Asset filtering uses the train segment only; validation and test are checked after selection.

## 1. 1h 空头上影拒绝 ATR1.0 资产筛选Top10

- candidateId: `v13_7_40_1h_short_rejection_2149_asset_filter_top10`
- plain meaning: 1h short-side upper-wick rejection with fixed 2R exit and train-only asset filter.
- selected assets: APE/USDT:USDT, APT/USDT:USDT, BTC/USDT:USDT, GALA/USDT:USDT, LTC/USDT:USDT, MANA/USDT:USDT, NEAR/USDT:USDT, SAND/USDT:USDT, SOL/USDT:USDT, TRX/USDT:USDT
- params: `{"upper_buffer": 0.006, "trend_tolerance": 1.0, "rsi_high": 60, "volume_min": 1.2, "stop_atr": 1.0, "max_hold": 12}`
- all sample: trades=219, winRate=51.1416%, PF=1.517, expectancyR=0.281784, maxDD(R)=10.9678
- validation: trades=64, winRate=43.75%, PF=1.0951, expectancyR=0.057736
- test: trades=65, winRate=50.7692%, PF=1.5075, expectancyR=0.285042, maxDD(R)=10.9678
- status: local sandbox / paper observation candidate only.

## 2. 1h 空头上影拒绝 ATR1.0 资产筛选Top10

- candidateId: `v13_7_40_1h_short_rejection_2148_asset_filter_top10`
- plain meaning: 1h short-side upper-wick rejection with fixed 2R exit and train-only asset filter.
- selected assets: APE/USDT:USDT, APT/USDT:USDT, BTC/USDT:USDT, GALA/USDT:USDT, LTC/USDT:USDT, MANA/USDT:USDT, NEAR/USDT:USDT, SAND/USDT:USDT, SOL/USDT:USDT, TRX/USDT:USDT
- params: `{"upper_buffer": 0.006, "trend_tolerance": 1.0, "rsi_high": 60, "volume_min": 1.2, "stop_atr": 1.0, "max_hold": 8}`
- all sample: trades=219, winRate=49.3151%, PF=1.4348, expectancyR=0.227261, maxDD(R)=11.8513
- validation: trades=64, winRate=42.1875%, PF=0.993, expectancyR=-0.003982
- test: trades=65, winRate=52.3077%, PF=1.5031, expectancyR=0.274872, maxDD(R)=10.3932
- status: local sandbox / paper observation candidate only.

## 3. 1h 空头上影拒绝 ATR1.0 资产筛选Top10

- candidateId: `v13_7_40_1h_short_rejection_2150_asset_filter_top10`
- plain meaning: 1h short-side upper-wick rejection with fixed 2R exit and train-only asset filter.
- selected assets: APE/USDT:USDT, APT/USDT:USDT, BTC/USDT:USDT, GALA/USDT:USDT, LTC/USDT:USDT, MANA/USDT:USDT, NEAR/USDT:USDT, SAND/USDT:USDT, SOL/USDT:USDT, TRX/USDT:USDT
- params: `{"upper_buffer": 0.006, "trend_tolerance": 1.0, "rsi_high": 60, "volume_min": 1.2, "stop_atr": 1.0, "max_hold": 16}`
- all sample: trades=219, winRate=49.3151%, PF=1.5112, expectancyR=0.290469, maxDD(R)=11.966
- validation: trades=64, winRate=45.3125%, PF=1.1929, expectancyR=0.119861
- test: trades=65, winRate=46.1538%, PF=1.3785, expectancyR=0.234747, maxDD(R)=11.966
- status: local sandbox / paper observation candidate only.

## 4. 1h 空头上影拒绝 ATR1.0 资产筛选Top8

- candidateId: `v13_7_40_1h_short_rejection_2077_asset_filter_top8`
- plain meaning: 1h short-side upper-wick rejection with fixed 2R exit and train-only asset filter.
- selected assets: APE/USDT:USDT, APT/USDT:USDT, BTC/USDT:USDT, GALA/USDT:USDT, LTC/USDT:USDT, NEAR/USDT:USDT, SOL/USDT:USDT, TRX/USDT:USDT
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.0, "rsi_high": 60, "volume_min": 1.2, "stop_atr": 1.0, "max_hold": 12}`
- all sample: trades=175, winRate=52.0%, PF=1.5545, expectancyR=0.299841, maxDD(R)=9.903
- validation: trades=46, winRate=43.4783%, PF=1.1085, expectancyR=0.067674
- test: trades=56, winRate=50.0%, PF=1.4233, expectancyR=0.241901, maxDD(R)=9.903
- status: local sandbox / paper observation candidate only.

## 5. 1h 空头上影拒绝 ATR1.2 资产筛选Top10

- candidateId: `v13_7_40_1h_short_rejection_2021_asset_filter_top10`
- plain meaning: 1h short-side upper-wick rejection with fixed 2R exit and train-only asset filter.
- selected assets: ADA/USDT:USDT, AXS/USDT:USDT, BTC/USDT:USDT, DOGE/USDT:USDT, GALA/USDT:USDT, LTC/USDT:USDT, NEAR/USDT:USDT, SAND/USDT:USDT, SOL/USDT:USDT, TRX/USDT:USDT
- params: `{"upper_buffer": 0.003, "trend_tolerance": 1.0, "rsi_high": 62, "volume_min": 1.2, "stop_atr": 1.2, "max_hold": 8}`
- all sample: trades=131, winRate=54.9618%, PF=1.685, expectancyR=0.262404, maxDD(R)=7.2055
- validation: trades=34, winRate=61.7647%, PF=1.7159, expectancyR=0.252051
- test: trades=34, winRate=52.9412%, PF=1.3186, expectancyR=0.153767, maxDD(R)=7.2055
- status: local sandbox / paper observation candidate only.
