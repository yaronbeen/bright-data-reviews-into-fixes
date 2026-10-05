# Handover 011 - Canonical Targets / R3

## Minimal Fix

- Independent collect-pending-resume case reproduced exclusion of the second approved input when the raw job used explicit port 443 but returned review URL was canonical.
- Two-line correction: choose the matching validated `planned_jobs` entry and pass its canonical URL list into the existing shared normalizer.
- Raw original job, manifest bytes/hash, tests, package/CLI identity, and request counts are unchanged. No new features, matrix, helper, or review dispatch.
- No edits to README, skills, or the separate docs-worker files. Detected concurrent README integration during build; rebuilt the final wheel once to include the worker's completed section byte-exactly.

## Verification

- RED: one failed case. GREEN: one passed on source and one passed on final fresh installed wheel.
- Full source suite: 187 passed in 1.22s; final installed suite: 187 passed in 1.15s.
- Installed module isolation five of five PASS; network syscalls denied.
- Compilation, clean pip check, goldens, nine existing CLI checks, source/installed secret scans passed.
- R3 wheel: `/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r3/reviews_into_fixes-0.1.0-py3-none-any.whl`.
- SHA-256: `21bee0cc67f25a00db7e9a7c4b794fb567357d9165847fc04a9b0fa83e9a72b9`.
- Evidence: `/home/yaron/projects/bright-data-reviews-into-fixes/VERIFICATION.md`.

## Naming / Gate

Latest user instruction sets the eventual remote name to `yaronbeen/bright-data-reviews-into-fixes`; package/CLI remain `reviews-into-fixes`. Earlier brand-neutral remote naming notes are superseded by this instruction.

No paid/live call, remote operation, stage, commit, push, or publication. Await main final focused approval. Live Web Unlocker remains disabled; provider live behavior is unverified. Five skill approvals belong to the separate docs-worker workflow, not an authorization to publish this candidate.
