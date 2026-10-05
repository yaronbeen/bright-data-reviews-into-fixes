# Resume Mapping And Transport Boundaries

## Reproduction

Independent tests in `/home/yaron/projects/bright-data-reviews-into-fixes/tests/test_resume_mapping_regressions.py` produced 19 failures and four passes on both source and the first frozen wheel. Tests remained unchanged throughout the repair.

## Root Causes

- Resume used the first batch URL as a blanket parent, bypassing the collect boundary's approved-target mapping and provider-error exclusions. This rewrote second-input citations and collapsed record IDs across distinct inputs.
- Normal/error-body reads could raise HTTPException/IncompleteRead outside the transport normalization boundary. HTTPError-body exceptions are not caught by sibling except clauses.
- URLError could wrap a timeout reason but was classified as a generic failure.
- JSON RecursionError escaped the post-dispatch boundary even though the response was under the byte limit.

## Fix

- Reuse one bounded Amazon response mapping/error-exclusion path in collect and resume. Keep exact approved multi-input URLs and sole-input attribution before identity normalization.
- Enclose both normal and HTTPError-body reads in the same transport normalization block; map HTTPException to fixed transport-error codes and inspect wrapped timeout reasons.
- Catch decoder recursion as invalid-response while still inside the counted request/receipt handling.
- Preserve prior sources/jobs/snapshots and actual counts via existing output/private recovery mechanisms; make no retry or retrigger.

## Verification

All 23 independent cases and the full 186-case suite pass on source and on a fresh isolated installed wheel. Installed module origins are checked, network syscalls are denied, tests retain their original hashes, and the prior wheel is retained for comparison.
