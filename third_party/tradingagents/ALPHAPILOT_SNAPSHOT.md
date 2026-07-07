# AlphaPilot Third-Party Snapshot: TradingAgents

This directory stores a vendored reference snapshot of 	auricresearch/tradingagents for AlphaPilot research architecture review.

- Upstream: https://github.com/tauricresearch/tradingagents.git
- Snapshot commit: 01477f9afb7a47b849ed4c9259d3a9a4738d9fda
- Snapshot captured at: 2026-07-07T00:55:45Z
- Upstream license: Apache License 2.0, preserved in LICENSE
- AlphaPilot usage: architecture reference for multi-agent research review, structured reports, checkpointing, and decision-memory ideas.

Important boundary:

AlphaPilot does not treat this snapshot as an executable trading adapter. Any upstream Buy, Sell, Trader, Portfolio Manager, simulated exchange, or transaction wording must be mapped into AlphaPilot research-only terminology before use. This snapshot must not create orders, connect Trade API, connect Withdraw API, store exchange API keys, read real account data, or automate trading.

Keep attribution and license notices when reusing code or adapting designs.