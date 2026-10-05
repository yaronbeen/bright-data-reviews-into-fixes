# Handover 008 - 2026-10-05

## Approval Replay-State Security Fix

- Moved persistent CLI nonce consumption from the caller-selected approval-file directory to an app-owned private state root: `$XDG_STATE_HOME/reviews-into-fixes/approval-consumption/` or `~/.reviews-into-fixes-state/reviews-into-fixes/approval-consumption/`.
- State traversal uses dirfd-relative `O_NOFOLLOW`/directory opens. Application directories require current-UID ownership and exact mode 0700; state-home ancestors are checked for ownership/write safety and symlinks.
- Marker files use exclusive no-follow creation, current-user ownership, mode 0600, single link, and fsync. Marker names bind approval ID+nonce; marker contents additionally bind the validated approval digest. Tampered markers fail closed.
- Added tests for hostile precreated modes, state-home/app/consumption symlinks, wrong-owner metadata, marker symlink/content tampering, approval-file-directory attacks, default home storage, and concurrent processes where exactly one consumer wins.

## Verification

- Full suite: 150 passed (`python3 -m pytest -q`, 0.59s).
- Focused app-state replay tests: 13 passed, 37 deselected.
- Clean wheel: `reviews_into_fixes-0.1.0-py3-none-any.whl`, SHA-256 `e3fdba536aea451506edb5fbdac87829700f7e1f72a70ce95fc1e95f9d1d639f`.
- Clean install, CLI version/demo, fixture byte comparison, `pip check`, compilation, and secret scan passed.
- No live calls, remote creation, commit, push, or publication.

## Release Gate

- Security and the three release perspectives remain unapproved. Independent reviewer dispatch fails with nested agent depth limit 1.
- Do not create a remote or publish until top-level reviewers return the required approvals.
