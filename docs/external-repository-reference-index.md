# External Repository Reference Index

Status: reference-only
Recorded at: 2026-07-06

This index records external repositories that AlphaPilot can study as design
references. It is not dependency installation, code copying, or execution
integration.

## Recorded References

| Repository | Local note | Use in AlphaPilot |
|---|---|---|
| `yydhYYDH/alpha101` | `docs/future-factor-research-reference-alpha101.md` | Factor panels, expression grammar, factor search, IC-style evaluation, research service ideas. |
| `ryckli/CryptoAgentPro.beta` | `docs/future-live-trading-reference-cryptoagentpro-beta.md` | Future live-trading boundary, paper/testnet separation, risk gateway, human confirmation, emergency controls. |

## Current Boundary

The index does not add:

- external repository dependencies
- copied source code
- exchange API key input or storage
- Trade API
- Withdraw API
- real account reads
- real position reads
- real order creation
- testnet execution
- automatic trading

Any future implementation that uses these references must go through a separate
AlphaPilot design boundary and safety review.
