# Learnings

## 2026-10-05

- Exact sentence-level positive cues must suppress a defect cue only in that sentence. A separate defect sentence remains eligible.
- Review identity is exactly `(kind, canonical URL, record_id)`; ID-less reviews use the canonical content hash in the final position. The same record ID at a different URL remains independent.
- Positive suppression is sentence-local. A positive sentence suppresses only its own defect cue and never removes other actionable sentences or unrelated review sources.
- Heading blocks are useful for structure but never count as instruction body evidence.
- Source hashes establish deterministic snapshot identity, not factual truth.
- Local record/request limits constrain this client but cannot cap provider work or billing.
- Dropping provider author/profile metadata does not anonymize names or sensitive details embedded in free text.
- Setuptools flat-layout auto-discovery considered fixture and handover directories as packages; package discovery must be explicitly restricted to `reviews_into_fixes*`.
- A clean virtual environment has no build backend. For a network-free install check, build the wheel with the host's pinned setuptools and install that wheel into the clean environment with `--no-index`.
- Multi-file reports need a prepare/commit/rollback transaction; three independent atomic renames can otherwise leave a mixed old/new artifact set.
- A trigger timeout is not an ordinary failed response because provider work may continue. Preserve `completion_unknown`, stop after one request, and require operator review rather than retrying.
- Environment-provided wall-clock overrides are unsafe in production approval gates. The CLI uses system UTC; only direct test boundaries accept an injected clock.
- A signed/hash-matched approval is still replayable without state. Pair a short-lived approval ID/nonce/content digest with atomic consumption in an application-owned private XDG/home state directory; never anchor replay protection beside a caller-selected approval file.
- Local API redirect rejection says nothing about redirects followed by a provider while fetching a target. Live Web Unlocker must remain disabled until final target scope can be verified through an official mechanism.
- Provider-returned URLs are untrusted data. Map single-input records to the approved target and reject ambiguous multi-input mappings instead of retaining arbitrary URLs or queries.
- Provider HTTP completion is not provider completeness. Receipt states describe only local processing and always preserve `provider_completeness: unknown`.
- Brand-neutral product naming keeps Bright Data accurately positioned as an optional integration rather than implying ownership, affiliation, or endorsement.
- Synthetic disclosure must be evidence-level: cards/CSV carry provenance flags, and mixed Markdown reports identify exact synthetic source IDs.
- Reject all query parameters on live Amazon targets, not only a denylist: undocumented parameter names can still carry credentials or tracking data.
- A resume approval's retention budget is cumulative across previously retained sources and the pending job's requested maximum, and must be checked before consuming the nonce or making the download call.
- CSV bidi defenses should remove directional formatting controls without indiscriminately deleting all Unicode format characters such as joiners used in legitimate text.
- CSV formula detection must also skip leading Unicode `Cf` format characters (for example zero-width or BOM characters) before checking spreadsheet formula prefixes; JSON keeps original evidence unchanged.
- Resume failures require their own accounting boundary: attach the updated receipt to the safe transport error after a GET, preserve prior sources and snapshot identity, and persist before reporting failure. Historical request totals and attempts in the current invocation are distinct.
- Collect and resume must share approved-target mapping and provider-error exclusions before normalization. Mapping every snapshot row to the first input destroys cross-URL review identity and can falsely deduplicate or conflict records.
- Body reads in an `HTTPError` handler can raise `http.client.HTTPException` too; both successful and HTTP-error reads must stay inside the same normalization boundary. `URLError.reason` can wrap `TimeoutError` and must retain completion-unknown classification.
- A bounded response can still exceed the JSON decoder's recursion depth. Catch `RecursionError` as invalid-response within post-dispatch handling so the actual request, pending snapshot, and recovery receipt are preserved.
- Resume normalization must use the matching validated canonical planned job, while retaining the raw original job and manifest hash in the receipt. Explicit default ports in approved raw URLs must not cause returned canonical records to be excluded.
- The descriptive public repository name can include `bright-data` without changing neutral distribution/module/CLI names or the independent-showcase/non-endorsement disclosures. The current explicit user naming instruction supersedes earlier remote-name notes, not historical decisions.
- Final core SHIP and separate skill approvals are user-reported; independent runtime evidence is a distinct PASS. Neither approval nor offline execution verifies live provider/account behavior.
- GitHub publication verification must check actual public bytes/HEAD and a credential-free clone, not only the authenticated creation result. The existing 187-test suite passed on both Python 3.11 and 3.12 in CI; the public clone separately passed offline CLI/golden checks with network denial.
