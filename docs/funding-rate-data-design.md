# Funding Rate Data Design

Funding rate is a future public market-context input for AlphaPilot research.
V13.4.28 only registers the schema; it does not collect funding data.

## Intended Use

Funding rate may help describe derivatives positioning context, especially for
bear-regime or crowded-trade analysis. It is not a trading signal and must not
trigger execution.

## Required Fields

```text
exchange
pair
marketType
timestamp
fundingRate
nextFundingTime
sourceId
qualityStatus
warnings
```

`fundingRate` and `nextFundingTime` may be null when the public source is
unavailable. Missing funding data must not be replaced with synthetic values.

## Quality Requirements

- store UTC timestamps
- keep null values when public data is unavailable
- record source limitations in warnings
- reject private/API-key sources
- do not infer favorable market context from missing funding

## Safety Boundary

Funding data is research context only. It does not use API keys, private
endpoints, account data, order data, Trade API, Withdraw API, or auto trading.
