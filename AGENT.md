# Agent Guide

## Start Here

1. Read the newest file in `/home/yaron/projects/bright-data-reviews-into-fixes/handover/`.
2. Review P0 items in `/home/yaron/projects/bright-data-reviews-into-fixes/TECH_DEBT.md`.
3. Skim `/home/yaron/projects/bright-data-reviews-into-fixes/LEARNINGS.md`.
4. Run `python3 -m pytest -q` from the repository root before and after changes.

## Purpose & Context

Reviews Into Fixes is a brand-neutral Python 3.11+ offline-first CLI with optional Bright Data integration. It converts explicitly selected review sentences into evidence-backed suggested investigation cards by joining exact cues, operator-defined areas, known issue phrases, and selected instruction passages. It does not validate defects, rank roadmap work, or promise that proposed checks are runnable.

Current status: version 0.1.0 R3 and its synthetic demo pass all 187 existing tests. The user reports final core QA/security/brand SHIP and separate skill approvals and authorizes public publication at `yaronbeen/bright-data-reviews-into-fixes`. The optional Bright Data adapter has not been verified against a live account and must remain labeled live-unverified. Live Web Unlocker is disabled. Read the latest handover for actual publication/CI state.

## Architecture / Design

```text
JSON payload/library
       |
       v
core.py: strict validation -> normalization -> exact rules -> report dict
       |                                           ^
       v                                           |
export.py: JSON / Markdown / CSV            brightdata.py
       |                                  offline import or
       v                                  explicitly gated HTTP
cli.py: atomic writes, flags, exit codes
```

- `/home/yaron/projects/bright-data-reviews-into-fixes/reviews_into_fixes/core.py`: pure analysis; no filesystem, environment, or network.
- `/home/yaron/projects/bright-data-reviews-into-fixes/reviews_into_fixes/export.py`: deterministic safe renderers.
- `/home/yaron/projects/bright-data-reviews-into-fixes/reviews_into_fixes/brightdata.py`: local provider normalization, planning, approval gates, bounded collection/resume DTOs.
- `/home/yaron/projects/bright-data-reviews-into-fixes/reviews_into_fixes/cli.py`: file operations, explicit environment reads for live mode, structured exits.

## Decisions Log

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-10-05 | Use standard-library Python and deterministic exact-phrase rules. | Keeps offline replay checkable and avoids hidden model behavior or keys. |
| 2026-10-05 | Preserve source citations, contrary reports, ambiguity, and overflow. | Prevents unsupported confidence and silent evidence loss. |
| 2026-10-05 | Require explicit approval, charge acceptance, credentials, zones, and injected/pinned transport for live collection. | Makes network and potential spend opt-in and bounded locally. |
| 2026-10-05 | Keep public fixtures entirely invented. | Avoids publishing third-party review content or personal data. |
| 2026-10-05 | Use exact `(kind, canonical URL, record ID or content hash)` identity. | Record IDs alone are not globally unique; conflicts must not erase unrelated evidence. |
| 2026-10-05 | Commit the three analysis artifacts transactionally. | Prevents a failed rename from leaving mixed report generations. |
| 2026-10-05 | Make approvals short-lived, nonce-bearing, and atomically single-use. | Manifest hashes and expiry alone do not prevent replay or concurrent use. |
| 2026-10-05 | Disable live Web Unlocker collection. | Local API redirect rejection cannot prove where provider-side target redirects resolve. |
| 2026-10-05 | Use brand-neutral release identity `reviews-into-fixes`. | Bright Data is an optional integration, not the product owner or endorser. |
| 2026-10-05 | Use locally scoped receipt states and `provider_completeness: unknown`. | Parsing a response cannot establish provider completeness or external success. |
| 2026-10-05 | Store approval replay markers in an app-owned private state directory, not beside approval input. | The approval path is operator-selected and may be precreated, symlinked, or writable by another principal. |
| 2026-10-05 | Publish the showcase as `yaronbeen/bright-data-reviews-into-fixes`; retain neutral package/CLI names. | The user explicitly requires the descriptive `bright-data` repository name and public visibility; disclaimers preserve the independent, non-endorsed integration boundary. |
| 2026-10-05 | Bundle the approved `review-next-check` Markdown skill and checked example locally. | Adds an evidence-bound use of generated reports without a new CLI feature, service, dependency, or global installation. |

## Runbook / Operations

Run tests:

```bash
python3 -m pytest -q
```

Regenerate the public expected artifacts after an intentional behavior change:

```bash
rm -rf /tmp/reviews-into-fixes-demo
python3 -m reviews_into_fixes analyze fixtures/demo.json --out-dir /tmp/reviews-into-fixes-demo
diff -ru fixtures/expected /tmp/reviews-into-fixes-demo
```

Do not regenerate expected artifacts blindly. Inspect citations, caveats, and synthetic banners. Never place real approvals, credentials, raw provider bodies, or private evidence in tracked fixtures.

For an invalid-input failure, expect exit 2 and structured stderr. For collection failures, never add retries or fallback endpoints. Pending snapshots require a new explicit `resume` invocation.

## API References

- Web Unlocker API: https://docs.brightdata.com/api-reference/rest-api/unlocker/unlock-website
- Scraper API synchronous requests: https://docs.brightdata.com/api-reference/scrapers/synchronous-requests
- Monitor progress: https://docs.brightdata.com/api-reference/scrapers/management-apis/monitor-progress
- Download snapshot: https://docs.brightdata.com/api-reference/scrapers/delivery-apis/download-snapshot
- Contract source: `/home/yaron/.claude/data/brightdata-drafts/2026-10-04-five-project-build-contract.md`

Recheck current provider documentation before changing or live-testing request shapes.

## Project File Structure

- `/home/yaron/projects/bright-data-reviews-into-fixes/reviews_into_fixes/`: application package.
- `/home/yaron/projects/bright-data-reviews-into-fixes/tests/`: independent acceptance tests; do not weaken them.
- `/home/yaron/projects/bright-data-reviews-into-fixes/fixtures/demo.json`: invented analysis input.
- `/home/yaron/projects/bright-data-reviews-into-fixes/fixtures/provider/`: invented provider-shaped exports.
- `/home/yaron/projects/bright-data-reviews-into-fixes/fixtures/expected/`: deterministic generated public artifacts.
- `/home/yaron/projects/bright-data-reviews-into-fixes/.github/workflows/test.yml`: Python 3.11/3.12 CI.
- `/home/yaron/projects/bright-data-reviews-into-fixes/skills/review-next-check/SKILL.md`: approved portable next-check memo instructions.
- `/home/yaron/projects/bright-data-reviews-into-fixes/docs/skills/`: checked invented example, historical validation, and public review-file manifest.

## References

- Learnings: `/home/yaron/projects/bright-data-reviews-into-fixes/LEARNINGS.md`
- Technical debt: `/home/yaron/projects/bright-data-reviews-into-fixes/TECH_DEBT.md`
- Handovers: `/home/yaron/projects/bright-data-reviews-into-fixes/handover/`
