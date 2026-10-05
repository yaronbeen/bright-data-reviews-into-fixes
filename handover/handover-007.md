# Handover 007 - 2026-10-05

## Security Re-review Findings Addressed

- Live Amazon URLs now reject every query parameter before approval consumption or transport, covering undocumented names such as `access_token` and tracking parameters.
- Resume validates cumulative retention (`prior retained_records + pending job requested maximum`) against the new approval before consuming the nonce or issuing a GET.
- CSV export strips Unicode bidi formatting controls before formula-prefix checks while retaining other format characters; JSON evidence remains unchanged.
- Added regressions for query rejection, page-plus-pending cumulative cap, bidi formula prefixes, and embedded bidi control removal.

## Verification

- Full suite: 140 passed (`python3 -m pytest -q`, 0.43s).
- Focused query/cumulative-cap/CSV controls: 14 passed.
- Compilation passed.
- Brand-neutral wheel built and installed cleanly, SHA-256 `b4b30fcf14fd070f813d58354c50245d83d96ea0dedc78866c70e1222d198489`; installed CLI and fixture comparison passed; `pip check` clean.
- TruffleHog reported zero verified and unverified secrets.
- No live calls, remote creation, commit, push, or publication.

## Release Gate

- Independent security review and the three release perspectives remain unapproved. Re-review dispatch continues to fail at nested agent depth limit 1.
- No remote or publication until top-level reviewers return the required approvals.
