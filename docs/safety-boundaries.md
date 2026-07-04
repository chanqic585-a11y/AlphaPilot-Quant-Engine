# Safety Boundaries

V13.2 safety rules:

- Do not connect real Trade API.
- Do not connect Withdraw API.
- Do not save real API Key.
- Do not read real exchange account balances.
- Do not read real exchange positions.
- Do not create real orders.
- Do not auto trade.
- Do not execute real dry-run trading.
- Do not expose REST API to the public internet.
- Do not hardcode exchange credentials.

Allowed in V13.2:

- Freqtrade config templates.
- Docker compose template.
- Strategy placeholder.
- Backtest command template.
- Data download command template.
- Mock report export.
- Proposal skeleton.
- Risk Gate skeleton.
- Audit Ledger skeleton.

Any future execution capability must be designed separately with:

- explicit Proposal records
- Risk Gate result
- Human Gate confirmation
- Broker Preflight
- protective-order verification
- Audit Ledger event
- emergency lock behavior
