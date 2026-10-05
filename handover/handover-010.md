# Handover 010 - Independent RED Repairs / R2

## Authorized Scope

Fixed only independently reproduced mapping, identity, transport-read/timeout, and JSON recursion defects. No helpers/reviewers, live calls, remote, stage, commit, or publication. Tests, README, and the separate docs worker's owned files were not edited.

## Fixes

- Collect and resume share approved Amazon target mapping and provider-error exclusions. Second inputs retain their own citation URL; ambiguous/out-of-scope multi-input rows are excluded; sole-input rows map to the approved parent.
- Same record IDs at distinct approved URLs no longer become false duplicates/conflicts.
- Real urllib normal and HTTPError-body reads normalize HTTPException/IncompleteRead. Wrapped timeout reasons produce completion-unknown and exit 4.
- JSON recursion becomes invalid-response within post-dispatch handling, preserving counted receipts and existing output/private recovery behavior.

## Verification

- Reproduced RED: 19 failed, four passed.
- Source independent file: 23 passed; source full suite: 186 passed.
- Fresh installed independent file: 23 passed; installed full suite: 186 passed, module isolation five of five PASS.
- Both full-suite runners used kernel network denial; tests remain byte-identical.
- Compile, goldens, nine CLI variations, clean pip check, source/installed secrets scans passed.

## Candidate / Gate

- R2 wheel: `/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r2/reviews_into_fixes-0.1.0-py3-none-any.whl`.
- SHA-256: `5377e014422ac328ad604bedc5ae2f2431701aa8242d8b67145d9c989f0e7593`.
- Previous candidate retained intact. Await main focused review and separate docs-worker return; no README overlap or worker-file edits.
- Live Web Unlocker remains disabled and provider live behavior remains unverified.
