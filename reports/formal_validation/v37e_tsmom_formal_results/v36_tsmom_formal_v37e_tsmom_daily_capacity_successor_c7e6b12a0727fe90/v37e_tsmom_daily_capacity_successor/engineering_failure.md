# V37E Formal Input Engineering Failure

- Status: remediated by successor freeze; this frozen campaign is not retried.
- Failure stage: funding schedule validation during Formal input loading.
- Root cause: the Formal loader measured funding gaps across rows before the frozen Formal window, while readiness measured only the Formal window.
- Formal run count: 0.
- Formal input read count: 0.
- Result read count: 0.
- Locked OOS access count: 0.
- Strategy conclusion: none. This was an implementation/parity failure, not a strategy-performance result.

The original freeze tag remains immutable. A new successor preregistration must include the window-alignment repair and pass remote freeze audit before any Formal result is produced.
