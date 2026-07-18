# V22 Formal Validation Summary

- Candidate: `auto-trend_failure_reversal-4h-short-v2`
- Route: `capital_infeasible`
- Assigned formal signals: 1258
- Stable capacity rejections: 1258
- Capital-accepted trades: 0
- Funding evidence: `actual_available`
- Future Locked OOS reads: 0
- Release eligible: no

The implementation and evidence chain passed preflight. The frozen capacity policy
rejected every event because verified quote-turnover semantics are unavailable in the
frozen data profile. This is an economic/capital infeasibility result, not an
implementation failure, and no gate was relaxed.
