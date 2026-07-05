# Open Interest Data Design

Open interest is a future public market-context input for AlphaPilot research.
V13.4.28 only registers the schema; it does not collect open-interest data.

## Intended Use

Open interest may help identify participation and leverage context around
trend, crash, or squeeze regimes. It is not a strategy by itself and must not
be interpreted as a trading command.

## Required Fields

```text
exchange
pair
marketType
timestamp
openInterest
openInterestCurrency
sourceId
qualityStatus
warnings
```

Open-interest units can differ by source. A value without an explicit unit must
be marked with a warning.

## Quality Requirements

- store UTC timestamps
- preserve source units
- keep null values when public data is unavailable
- do not fabricate or rescale unknown units
- reject private/API-key sources

## Safety Boundary

Open-interest data is research context only. It does not use API keys, private
endpoints, account data, order data, Trade API, Withdraw API, or auto trading.
