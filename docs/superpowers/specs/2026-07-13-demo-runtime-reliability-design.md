# Demo Runtime Reliability Design

## Goal

Make OKX Demo execution auditable and self-diagnosing so the console distinguishes zero evaluated strategies from evaluated strategies with zero matches.

## Decision

Two approaches were considered:

1. Keep the WebSocket-only trigger and improve UI wording. This remains unable to explain or recover from a missing close event.
2. Keep WebSocket confirmed closes as the execution source, add durable runtime-health and close-event audit records, and add a watchdog that restarts only the public market runtime when it is stopped or disconnected. This retains fail-closed execution while making failure visible and recoverable.

Use approach 2. No REST-synthesized close event will be used to place orders in this patch. The watchdog may reconnect and reseed public data, but only a confirmed WebSocket close event can enter strategy evaluation.

## Boundaries

- Do not modify immutable Demo Releases or strategy rules.
- Do not bypass public-market warmup, order, risk, idempotency, or account gates.
- Do not persist API credentials or add Withdraw support.
- Do not enable Live execution.
- Runtime recovery must not create an order without a confirmed close event.

## Behavior

- Persist bounded runtime observations: startup, warm, disconnected, reconnecting, recovered, confirmed close received, evaluation started, and evaluation completed.
- Store timestamps, timeframe, close sequence, runtime blockers, evaluated release count, matched signal count, and order count; never store credentials.
- The runner checks public runtime health on heartbeat. If Demo is desired and armed but the public runtime is not running or connected, it attempts bounded recovery and records the outcome.
- A confirmed close event is acknowledged before evaluation and linked to the completed heartbeat record.
- Projection text must show one of: not evaluated, evaluated with zero matches, evaluated with matches, or blocked before evaluation.

## Verification

1. Test-first runner tests prove a cold runtime triggers bounded recovery and does not evaluate without a close event.
2. Runtime tests prove disconnect/reconnect and confirmed-close observations are emitted without credentials.
3. Controller/store tests prove one close sequence produces one evaluation audit chain.
4. Projection tests prove zero evaluated is not rendered as zero matched.
5. Full Console tests, compileall, safety scan, and `git diff --check` must pass.

## Operational Rollout

Start the Console without credentials for public-runtime soak validation first. Re-enter process-only Demo credentials only after the public runtime emits a confirmed-close audit record. Then arm Demo and verify one immutable Release checkpoint before restoring the full batch.
