# Handover 009 - Frozen Candidate

## Scope

User froze scope. Finished only known approval-state hardening verification and resume transport/parse/output-failure request accounting and durable recovery. No nested reviewer dispatch or depth retry.

## Corrections

- Added 13 failing resume regressions before implementation, covering transport timeout/errors, HTTP/header errors, JSON/array failures, pending responses, target write failures, and failed recovery storage.
- Resume errors now preserve cumulative request counts, prior sources, pending snapshot/job IDs, and safe warnings in a durable saved library before reporting failure.
- Per-invocation GET count is reported separately as `requests_this_run`; no retry or new POST is made.
- Failed download receipts can be explicitly resumed later with a new approval. Output failure uses the existing private recovery mechanism and keeps the accurate counts.
- Verified the existing app-owned approval-state protections, including exactly one winner across two processes.

## Candidate

- Wheel: `/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0/reviews_into_fixes-0.1.0-py3-none-any.whl`.
- SHA-256: `c1fa2eebf3bc782a171f47817da1fd2c620f800a8a6ccab29143756b8d58275e`.
- Full source and installed-package suites: 163 passed each.
- Resume/CLI slice: 23 passed; approval-state slice: 13 passed.
- Installed CLI, clean `pip check`, compilation, and byte-identical goldens verified.
- Evidence: `/home/yaron/projects/bright-data-reviews-into-fixes/VERIFICATION.md` and `/home/yaron/projects/bright-data-reviews-into-fixes/RELEASE_CANDIDATE.md`.

## Gate

Candidate awaits the main focused reviewer. Live Web Unlocker remains disabled; provider live behavior remains unverified. No live calls, remote, commit, push, or publication. Do not expand scope or replace the frozen wheel absent a reproduced defect.
