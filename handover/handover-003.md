# Handover 003 - 2026-10-05

## Security Fixes

- Production CLI approval time now uses system UTC and ignores `REVIEWS_INTO_FIXES_NOW`; direct `now` injection remains a test boundary.
- Approvals require strict types, canonical URLs, ID, 64-hex nonce, issued/expiry timestamps, and a maximum 15-minute lifetime.
- Approval use is atomic and single-use before transport. CLI markers persist beside private approvals; direct library calls use a locked process-local set.
- Cumulative retention approval counts selected pages as one each plus requested review records.
- Live Web Unlocker is disabled because provider-side final redirect scope cannot be verified.
- Provider record URLs map to approved targets or are excluded.
- Pending 202/409 responses with error headers or explicit error bodies fail safely.
- File reads are bounded and restricted to regular non-symlink files.
- Markdown punctuation is entity-encoded and CSV formula defenses cover adversarial prefixes after whitespace/control characters.
- Git ignores `.env*`, private approvals/receipts/libraries, outputs, and consumption markers.

## Current State

- Final complete suite: 119 passing tests.
- Focused security/provider/CLI suite: 51 passing tests.
- Wheel SHA-256: `508211ddf8672b470d2848cb5940bebc7a36abf2ba503e75231d9c5d563e7c8f`.
- Clean installation, installed CLI replay, byte fixture comparison, `pip check`, compilation, and secret scan passed.
- TruffleHog reported zero verified and zero unverified secrets.
- No live calls, publication, remote creation, commit, or push occurred.
- Live Amazon collection remains mock-verified only; live Web Unlocker remains intentionally unavailable.
