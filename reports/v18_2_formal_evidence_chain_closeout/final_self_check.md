# AlphaPilot V18.2 Final Self-Check

## Identity and immutability

- V18 predecessor tag: `v13.27.1.18`.
- V18.1 predecessor tag: `v13.27.1.18.1`.
- V18.1 result manifest: `sha256:8068414f302fea0cc21d1b6907487ec374aeedbd9c10f8b16358d09dda4a05a5`.
- V18.1 result-read trial increment: `1`; it is operational lineage, not valid S01 economic evidence.
- V18.2-r2 campaign: `advisory_r_v18_2_s01_formal_evidence_chain_correction_e100fc1eafa9abd0`.
- Candidate: `s01_bear_idiosyncratic_selloff_recovery_4h`.
- Implementation commit: `a95552913139bbf579d5e1e961880d987728ae48`.
- Preregistration commit/tag: `305a934a8c99e20185ea2bd2d7f1213e9985b224` / `v13.27.1.18.2-r2`.
- Freeze commit: `6d88ad369f266a2f0c4c176273e3fc5e3fbfc957`.
- Authorization commit: `e36a9e59c617fbe016cd8303db4348a7cd010a2f`.
- Result commit: `6752c721b39578cf7d4aec1569c55e0d77745452`.
- Result manifest: `sha256:a9b499063547c5a3db131c749b5db404ffed2c5160eb39c8c9aa03a75809129b`.

## Frozen contracts and pre-result certification

- Strategy, ExitPolicy, capital policy, gates, universe, split, costs, benchmark, and statistical policy changes: `0`.
- Certification: `formal_evidence_chain_certification_95f9253c8c57d441c64d9172fc27cfc0b9bfeefca86525f7a7e6ce3f09b8e87a` (`certified`).
- Exact Freqtrade runtime loaded: yes; silent fallback: no; network access: `0`.
- Candidate-neutral core import violations: `0`; second synthetic candidate fixture: passed.
- Future Locked OOS access/content/metric reads: `0 / 0 / 0`.

## Formal result

- Claim / attempt / result / read counts: `1 / 1 / 1 / 1`.
- Raw signals: `884`; accepted trades: `0`; rejected signals: `884`.
- Rejections: unassigned signal `466`, ranking field unavailable `417`, cross-fold event `1`.
- Canonical identity mapping audit: `100%`, collisions `0`, unmapped internal/Freqtrade `0 / 0`.
- Signal identity / exit-leg parity: `100% / 100%`.
- Fold audit: `417` assigned, `467` explicitly rejected, `466` still marked unassigned, cross-boundary leakage `0`.
- Ranking and PIT parity: `100% / 100%`, but `417` real events lacked a frozen ranking field and were rejected.
- Capital acceptance / position-size parity: `100% / 100%`.
- Capacity semantics implementation: complete; known data units `9 / 20` (`45%`), unavailable symbols rejected.
- Funding: same-exchange history unavailable for `20 / 20`; no zero fabrication; funding gate not evaluable.
- Five folds and Base / 1.5x / 2x costs: zero accepted trades, PF `undefined_no_losses`, average and total Net R `0`.
- Same-event benchmark: zero accepted events; incremental Net R `0`.
- Newey-West: sample `1939`, alpha `0`, one-sided p `0.5`.
- BH / DSR / PBO / White RC / SPA: `unavailable_predeclared`; no result was fabricated.

## Mechanical route and safety

- Final route: `implementation_invalid_requires_new_campaign`.
- Primary blocker: `canonical_event_identity_mapping_incomplete`, caused by the real Fold/ranking evidence path, not S01 economics.
- Strategy performance failure: false; result-driven repair in this campaign: prohibited.
- Formal Pass: false; Formal Evidence: `0`; Release: `0`; Demo ARM: false; Orders: `0`.

## Next campaign

Create a new preregistered campaign. Before another formal result, prove on real-like fixtures that every event is either assigned to exactly one Fold or carries a distinct preregistered exclusion status, and that every assigned event has immutable ranking evidence. Do not change S01 parameters, ExitPolicy, policy values, gates, universe, split, or costs from this result.

## Validation

- Formal-validation tests: `166 passed`.
- Full AlphaPilot suite: `926 passed, 157 subtests passed` using `tests --import-mode=importlib`.
- Compileall, config validation, safety scan, Git diff check, JSON parse, and `54`-artifact hash verification: passed.
