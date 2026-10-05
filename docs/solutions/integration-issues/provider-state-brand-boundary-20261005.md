# Provider State And Brand Boundary

## Problem

The integration used provider-sounding `complete`/`failed` receipt states, assumed one Web Unlocker response shape, omitted evidence provenance from primary rows, and embedded the provider name in the distribution identity. These choices could imply provider completeness, ownership, or endorsement that local parsing cannot establish.

## Symptoms

- A locally parsed response was labeled `complete`.
- Web Unlocker JSON envelopes were rejected even though the current API reference documents `{status_code, headers, body}`.
- Mixed synthetic/operator reports showed only a generic synthetic banner.
- The wheel was named `bright_data_reviews_into_fixes`.

## Solution

- Use local states `processed`, `processed_with_exclusions`, `empty`, `pending`, and `transport_failed`; retain `completion_unknown` for trigger timeouts and `not_attempted` for untouched jobs.
- Add `provider_completeness: unknown` to every receipt.
- Parse direct raw Markdown and validated Web Unlocker envelopes to the same canonical text path. Envelope status and error headers are checked before body normalization.
- Add ordered provenance and `contains_synthetic_data` to cards and CSV rows; list exact synthetic source IDs in Markdown.
- Rename the distribution and future remote to `reviews-into-fixes`, while describing Bright Data only as an optional integration.
- Reference current Scraper API synchronous, monitor-progress, download-snapshot, and Web Unlocker API documentation.

## Prevention

Keep provider transport state separate from local processing state. Never turn a successfully parsed response into a claim of provider completeness, and keep integration vendors out of product identity unless ownership or endorsement is explicit.
