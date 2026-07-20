# V47-V50 Portfolio OOS Research Implementation Plan

1. Add tests for V46 publish verification, selection trial accounting, and missing upstream selection history.
2. Add tests that freeze the exact V46 sleeves and `pair_14d_cooldown` policy into a new V49 identity without reading results.
3. Implement a report generator that writes the V47 verification and V49 identity artifacts plus an artifact manifest.
4. Generate evidence from the published V46 commit and current immutable report set.
5. Run targeted and full tests, compile checks, safety scans, and `git diff --check`.

V48 engineering order smoke and V52 release approval are explicitly excluded because they require separate exact-hash approval and process-only Demo credentials.
