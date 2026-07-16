# V13.27.1.14 Acceptance

- Pre-migration active 2R reference hits inventoried: 32
- Fixed issue classes: 4
- Historical evidence hits preserved: 6,879
- Exit modes: fixed R, partial then trailing, structure or time, and hybrid all passed focused tests
- Legacy serialized bytes and execution parity: passed
- New exit-policy hash stability: passed
- Console v1/v2 import: passed
- Live admission boundary: unchanged and covered by an explicit regression test
- New campaigns: 0
- Holdout accesses: 0
- Releases: 0
- Demo ARM: false
- Orders: 0

The full first-party Quant run completed 694 tests and 157 subtests. Its only
failure is already present at tag `v13.27.1.13`: a historical sidecar stores the
SHA-256 of CRLF bytes while `.gitattributes` checks out the artifact as LF. V14
does not rewrite that immutable historical artifact or sidecar. All V14-focused
tests, compilation, configuration validation, safety checks, and diff checks
passed. The Console full suite passed 429 tests.
