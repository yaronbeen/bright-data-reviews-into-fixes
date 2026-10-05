# Approval Replay And Provider Target Scope

## Problem

The first live gate validated a manifest hash and expiry but allowed approval replay, trusted a caller-controlled environment clock, omitted selected pages from retention budgets, and accepted provider-returned record URLs. It also described redirects too broadly even though the local client controls only API redirects, not provider-side target navigation.

## Symptoms

- The same approval could trigger collection more than once.
- `REVIEWS_INTO_FIXES_NOW` could move production approval time backward.
- A page request consumed no retention allowance.
- A returned profile URL or sensitive query could become a citation URL.
- A clean local `api.brightdata.com` response could not establish the final Web Unlocker target.

## Root Cause

The approval was treated as static configuration rather than a consumable capability, and transport boundaries conflated the local API hop with provider-side retrieval.

## Solution

- Require strict UTC `issued_at`/`expires_at`, maximum 15-minute lifetime, ID, 64-hex nonce, exact types, canonical approved URLs, and cumulative page/record retention.
- Atomically consume approval ID/nonce/content digest before transport. The CLI creates an exclusive marker under an app-owned XDG/home state directory via safe directory descriptors, verifies current-user ownership/mode/no-symlink conditions, rejects unsafe existing markers, and binds marker data to approval content; direct in-process calls use a locked one-use set.
- Ignore environment clocks in production and use current system UTC.
- Apply one monotonic 75-second deadline to a collection invocation.
- Map single-input provider records to the approved target; require exact approved mapping for multi-input records.
- Reject every query parameter on live Amazon target URLs rather than relying on a partial sensitive-key denylist.
- Before resume, ensure the new retention allowance covers already retained sources plus the pending job's maximum requested records.
- Reject pending 202/409 responses carrying error headers or explicit error bodies.
- Disable live Web Unlocker until an official response can verify final target redirect scope.
- Bound reads to regular, non-symlink files and ignore private environment, approval, receipt, and marker files.

## Prevention

Model approvals as capabilities with lifecycle state, not booleans. Document each network boundary separately and never infer provider-side navigation guarantees from local HTTP client behavior.
