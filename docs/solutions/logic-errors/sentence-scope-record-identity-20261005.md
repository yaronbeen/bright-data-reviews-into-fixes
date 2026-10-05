# Sentence Scope And Record Identity

## Problem

The first implementation made two deterministic-analysis mistakes: one review containing a positive and a defect sentence suppressed cards from unrelated sources, and a non-null record ID was treated as globally unique without its canonical source URL.

## Symptoms

- `Setup no longer fails. Setup fails.` caused unrelated request and documentation cards to disappear.
- Two records with ID `R1` at different review URLs were treated as conflicting.
- True conflicting records did not force report status `needs_review`.

## Failed Approach

A `mixed_sources` filter was added to satisfy an incorrect RF06 assertion. This selected one entire source after sentence classification and violated the contract's same-sentence suppression rule. Identity was also shortened to `(kind, record_id)`, contradicting the shared canonical identity tuple.

## Root Cause

The implementation optimized for a mistaken test expectation instead of rechecking the governing contract. Sentence classification and record deduplication are independent boundaries and require their complete scopes.

## Solution

- Remove source-wide mixed-review filtering.
- Apply positive suppression only while classifying the same sentence.
- Use `(kind, canonical URL, record_id)` and substitute canonical content hash only when the record ID is null.
- Exclude both sides of a true conflict, retain unaffected cards, exclude conflicts from counts, and set `status: needs_review`.
- Correct RF05/RF06 and add independent duplicate, conflict, hash-fallback, and same-ID/different-URL regressions.

## Prevention

When a test and contract disagree, preserve the contract and document the test correction. Keep one regression per identity dimension and avoid source-level filters for sentence-level rules.
