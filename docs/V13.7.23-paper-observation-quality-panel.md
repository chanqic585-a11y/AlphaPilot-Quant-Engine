# AlphaPilot V13.7.23 - Paper Observation Quality Panel

V13.7.23 adds a report-only scoring model for the five V13.7.21 local paper-observation tasks.
The desktop console can combine these rules with local logs to show which strategies deserve attention first.

## Summary

- Task count: 5
- Not started count: 5
- Target closed samples total: 130
- Dry-run approved: False
- Live trading approved: False

## Quality Labels

- `not_started`: 未开始 - No local observation logs yet.
- `needs_more_logs`: 需要补日志 - Some logs exist, but log coverage is still thin.
- `continue_observing`: 继续观察 - Logs and rule matches are developing, but closed samples are not enough yet.
- `priority_watch`: 优先观察 - Good log coverage, rule matches, and low risk-warning pressure.
- `needs_risk_review`: 需要风险复核 - Invalidation or risk-warning logs are becoming material.
- `pause_candidate`: 暂停候选 - Enough observation exists to show poor signal availability or risk pressure.

## Safety Boundary

- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account or position reads.
- No order creation.
- No exchange Dry-run.
- No live or automatic trading.
