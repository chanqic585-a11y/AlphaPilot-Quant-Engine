# V13.27.1.11 Data Readiness

- Status: `data_not_ready`
- Formal ready directions: `0` / `2` required
- Campaign may run: `false`
- Decision: public-data evidence is committed; no campaign or holdout is run when data is not ready.

## Direction Gaps

- `A1`: formal=False; missing=verifiedSameExchangeOhlcv, historicalOpenInterest, realLiquidation, sameExchangeCoreFields
- `A2`: formal=False; missing=verifiedSameExchangeOhlcv, historicalOpenInterest, sameExchangeCoreFields, realLiquidation
- `B`: formal=False; missing=sameExchangeVerifiedPerpetualOhlcv, sameExchangeHistoricalFunding, sameExchangeHistoricalOpenInterest, sameExchangeHistoricalSpotPerpetualBasis
- `C`: formal=False; missing=pitTradability, pitLiquidity, listingDelisting, historicalContractUniverse
