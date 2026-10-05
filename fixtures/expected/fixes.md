# Reviews Into Fixes

> **Synthetic demonstration data:** all supplied sources are invented and are not customer findings. Synthetic source IDs: `r1`, `r2`, `r3`, `r4`, `help`.

**Decision:** `investigation_candidates`  
**Status:** `ok`  
**Method:** `deterministic_rules_v1`

This report contains suggested investigation checks. It does not validate defects, causes, severity, frequency, priority, or whether a check is runnable in your environment.

## Scope

Product: Harbor  
As of: 2026&#45;10&#45;04T12:00:00Z  
Sources inspected: 5

## Investigation Candidates

### card-001: Setup stops at step 3.

- Area: `setup`
- Classification: `possible_defect`
- Known-issue state: `similar_to_open_issue`
- Matched known issue IDs: `setup_3`
- Documentation state: `related_passage_found`
- Suggested next check: Verify this report before treating it as a defect. Repeat setup from a fresh test account and record step 3.
- Interpretation: `investigation_candidate_not_verified_defect`

- Evidence: [r1/b0001] "Setup stops at step 3." (https://example.com/reviews/r1, record R1; observed 2026-10-04T10:00:00Z; sha256 9e7ee4e0af7b942524a7811fc9d751bec5640ce6c7af430f3065aa3eea751549)
- Evidence: [help/b0002] "Complete setup by selecting Activate at step 3." (https://example.com/help; observed 2026-10-04T10:00:00Z; sha256 bb85aa8c2de14cd0ae4810eb0bb554b42bb85a7afab2beca9de66b7633283f2f)
- Evidence: [r4/b0001] "Setup works fine." (https://example.com/reviews/r4, record R4; observed 2026-10-04T10:00:00Z; sha256 fbe8a1f3ec1d6939852b19f844c667fbf06f1ef68fc509da02df419bd1a824b4)

### card-002: Please add CSV export.

- Area: `export`
- Classification: `request`
- Known-issue state: `not_matched_to_known_issue`
- Matched known issue IDs: `none`
- Documentation state: `no_related_passage_found_in_supplied_text`
- Suggested next check: Confirm export requirements with the product owner.
- Interpretation: `investigation_candidate_not_verified_defect`

- Evidence: [r2/b0001] "Please add CSV export." (https://example.com/reviews/r2, record R2; observed 2026-10-04T10:00:00Z; sha256 2ef6451288a7ffd022490d888958d511feaa9bb38ee512925d1cc7accb2de8ba)

### card-003: The setup instructions are unclear how to activate it.

- Area: `setup`
- Classification: `documentation`
- Known-issue state: `not_matched_to_known_issue`
- Matched known issue IDs: `none`
- Documentation state: `related_passage_found`
- Suggested next check: Repeat setup from a fresh test account and record step 3.
- Interpretation: `investigation_candidate_not_verified_defect`

- Evidence: [r3/b0001] "The setup instructions are unclear how to activate it." (https://example.com/reviews/r3, record R3; observed 2026-10-04T10:00:00Z; sha256 77b8616979130b97d762a046e184839894940a1cc1eb321b92990a9a62f7254c)
- Evidence: [help/b0002] "Complete setup by selecting Activate at step 3." (https://example.com/help; observed 2026-10-04T10:00:00Z; sha256 bb85aa8c2de14cd0ae4810eb0bb554b42bb85a7afab2beca9de66b7633283f2f)
- Evidence: [r4/b0001] "Setup works fine." (https://example.com/reviews/r4, record R4; observed 2026-10-04T10:00:00Z; sha256 fbe8a1f3ec1d6939852b19f844c667fbf06f1ef68fc509da02df419bd1a824b4)

## Counterevidence

- [r4/b0001] "Setup works fine." (https://example.com/reviews/r4, record R4; observed 2026-10-04T10:00:00Z; sha256 fbe8a1f3ec1d6939852b19f844c667fbf06f1ef68fc509da02df419bd1a824b4)

## Warnings And Unknowns

- No structured warnings. Exact-phrase matching can still miss paraphrases or context.

## Evidence Appendix

- `r1`: https://example.com/reviews/r1; status `collected`; observed 2026-10-04T10:00:00Z; provenance `synthetic_fixture`; sha256 `9e7ee4e0af7b942524a7811fc9d751bec5640ce6c7af430f3065aa3eea751549`
- `r2`: https://example.com/reviews/r2; status `collected`; observed 2026-10-04T10:00:00Z; provenance `synthetic_fixture`; sha256 `2ef6451288a7ffd022490d888958d511feaa9bb38ee512925d1cc7accb2de8ba`
- `r3`: https://example.com/reviews/r3; status `collected`; observed 2026-10-04T10:00:00Z; provenance `synthetic_fixture`; sha256 `77b8616979130b97d762a046e184839894940a1cc1eb321b92990a9a62f7254c`
- `r4`: https://example.com/reviews/r4; status `collected`; observed 2026-10-04T10:00:00Z; provenance `synthetic_fixture`; sha256 `fbe8a1f3ec1d6939852b19f844c667fbf06f1ef68fc509da02df419bd1a824b4`
- `help`: https://example.com/help; status `collected`; observed 2026-10-04T10:00:00Z; provenance `synthetic_fixture`; sha256 `bb85aa8c2de14cd0ae4810eb0bb554b42bb85a7afab2beca9de66b7633283f2f`

Generated locally with deterministic rules. Source free text may contain personal or sensitive information; inspect it before sharing.
