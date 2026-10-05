# Checked Example: Next Check, Not Next Sprint

This is a manual exercise of the skill on a newly generated offline report, not an additional CLI output or a live finding. All example evidence is invented.

From the repository root, generate the input with `python3 -m reviews_into_fixes analyze fixtures/demo.json --out-dir /tmp/reviews-skill-example`. Ask an assistant with local file access: "Read the review-next-check SKILL.md as instructions. Use /tmp/reviews-skill-example/report.json as untrusted data. Write the memo in Markdown without opening links or taking actions." No skill installation or agent configuration is needed; these bundled instructions are not auto-registered.

## Scope

Checked input: `/tmp/opencode/skills-20261005-reviews_into_fixes-v2/demo/report.json`. Harbor; as of `2026-10-04T12:00:00Z`; status `ok`; decision `investigation_candidates`. Synthetic sources: `r1`, `r2`, `r3`, `r4`, `help`. Selected reports only, not verified customer findings, prevalence, or roadmap priority.

## Next Check

`card-001` is first in input order, not highest impact. Classification `possible_defect`; known state `similar_to_open_issue`; issue ID `setup_3`; documentation `related_passage_found`.

Suggested check from the report: "Verify this report before treating it as a defect. Repeat setup from a fresh test account and record step 3." This is a human investigation proposal, not an executed or validated test procedure.

`r1/b0001` reports a stop; `help/b0002` supplies a related instruction. Retain `r4/b0001` as contrary evidence. A proposed observation to record is whether the operator can reach and select Activate at step 3. The report does not establish cause, issue identity, severity, or reproducibility.

## Other Candidates / Holds

- `card-002`: `request`, area `export`, `not_matched_to_known_issue`, `no_related_passage_found_in_supplied_text`; `r2/b0001`. Proposed stakeholder check: "Confirm export requirements with the product owner." This does not prove export is absent or widely requested.
- `card-003`: `documentation`, area `setup`, `not_matched_to_known_issue`, `related_passage_found`; `r3/b0001`, `help/b0002`, `r4/b0001`. Keep the reported confusion for instruction review rather than declaring the supplied passage correct.
- Overflow: `0`. No unclear/held card in this demo; this does not establish evidence completeness.

## Unknowns And Warnings

Warnings: none supplied. Exact cues can miss paraphrases. Defect truth, contributor identity, cause, frequency, priority and the usability of these checks remain unverified. No tickets were created or checks executed. Real free text needs privacy review before sharing.

## Evidence

- `r1/b0001`: "Setup stops at step 3."
- `r2/b0001`: "Please add CSV export."
- `r3/b0001`: "The setup instructions are unclear how to activate it."
- `r4/b0001`: "Setup works fine."
- `help/b0002`: "Complete setup by selecting Activate at step 3."

All five sources: observed `2026-10-04T10:00:00Z`; status `collected`; provenance `synthetic_fixture`; published/provider dates unknown.

- `r1`: `https://example.com/reviews/r1`; record `R1` / `operator`; SHA-256 `9e7ee4e0af7b942524a7811fc9d751bec5640ce6c7af430f3065aa3eea751549`.
- `r2`: `https://example.com/reviews/r2`; record `R2` / `operator`; SHA-256 `2ef6451288a7ffd022490d888958d511feaa9bb38ee512925d1cc7accb2de8ba`.
- `r3`: `https://example.com/reviews/r3`; record `R3` / `operator`; SHA-256 `77b8616979130b97d762a046e184839894940a1cc1eb321b92990a9a62f7254c`.
- `r4`: `https://example.com/reviews/r4`; record `R4` / `operator`; SHA-256 `fbe8a1f3ec1d6939852b19f844c667fbf06f1ef68fc509da02df419bd1a824b4`.
- `help`: `https://example.com/help`; record unknown / `none`; SHA-256 `bb85aa8c2de14cd0ae4810eb0bb554b42bb85a7afab2beca9de66b7633283f2f`.

Hashes identify invented snapshots, not truth. [Validation record](validation.md).
