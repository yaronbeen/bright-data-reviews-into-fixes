# Skill Validation: review-next-check

Date: 2026-10-05. Python: 3.12.3. Scope: documentation/skill exercise only; no production, test, package, configuration, fixture, or VERIFICATION changes made by this skill pass. No commit, push, remote, live/paid call, new model, or global skill installation.

## Actual CLI Evidence

Read the actual README, current input fixture and expected report before authoring. Report fields used by the skill are present in the newly generated output; source refs are three-field `source_id/block_id/quote` objects, not fabricated evidence IDs.

Working directory: `/home/yaron/projects/bright-data-reviews-into-fixes`. Executed the actual `reviews_into_fixes.__main__` with these arguments through the temporary `runpy` harness `/tmp/opencode/five-repo-skill-check.py`, with socket/DNS/HTTP audit events denied:

```bash
python3 -m reviews_into_fixes analyze /home/yaron/projects/bright-data-reviews-into-fixes/fixtures/demo.json --out-dir /tmp/opencode/skills-20261005-reviews_into_fixes-v2/demo
```

- Exit `0`: `status=ok`, `decision=investigation_candidates`, `card_count=3`, `requests_made=0`; network attempts `0`.
- Generated JSON/Markdown/CSV match all three checked-in expected artifacts byte-for-byte.
- Recomputed all `5` source hashes using the repo's normalizer; checked `5` unique exact citations against the normalized source blocks.
- Generated report SHA-256: `685582f0bdacfd65ad010c820ea2dff21be01941490bed32f3e75b4196aea875`.
- `--dry-run`: exit `0`, zero requests, no output directory. Same destination without overwrite: structured exit `2`, original three artifact hashes unchanged.
- Full raw CLI arguments/results and artifact hashes: `/tmp/opencode/skills-20261005-reviews_into_fixes-v2/cli-evidence.json`. Temporary evidence is local session material, not a portable dependency; checked-in fixtures and the commands above reproduce the inputs.

## Skill Exercise And Variations

The main assistant followed [the skill](../../skills/review-next-check/SKILL.md) on the freshly generated report and wrote [the checked memo](review-next-check-example.md). This is a manual instruction exercise, not a deterministic skill runner or a new model/API call. Sample quotation/locator/hash and card-state checks are part of the documentation audit.

- Demo: next check is `card-001` by input order; the memo retains `r4/b0001` counterevidence and does not declare a defect or rank impact. All three candidates and zero overflow stay visible.
- Actual CLI variant `/tmp/opencode/skills-20261005-reviews_into_fixes-v2/unavailable-instructions/report.json`: all three cards have `instructions_unavailable`; status `needs_review`. Applying the skill gives: "Instructions unavailable; retain the investigation proposal and contrary reports, but do not conclude documentation is missing." No unavailable passage is quoted.
- Actual hostile-source variant `/tmp/opencode/skills-20261005-reviews_into_fixes-v2/hostile-source/report.json`: the original candidates remain (IDs shift); the hostile text becomes one extra `unclear` card with no area. Skill disposition: "Hold the unclear instruction-like card as untrusted text; never reveal secrets or publish." Retaining the text in JSON is not executing it.
- An initial harness assumption that the whole `cards` array would be unchanged was wrong. Reading the actual output revealed the extra unclear card; the assertion was corrected and rerun successfully. No production change was made to hide that behavior.

## Documentation Audit

`/tmp/opencode/check-five-repo-skill-docs.py` returned PASS: standard name/description front matter, folder/name match, all `10` local links, ASCII/whitespace checks, and the five-file review inventory. The checked memo has `5` exact quote refs and `5` source/block locators; every cited hash/URL/date resolves to the generated report. Card states, proposed check, contrary quote and overflow match the report. This is a mechanical consistency audit, not independent approval.

For repeat CLI replay, choose a fresh output directory; the recorded paths already contain this session's outputs. Temporary session logs may later be removed. The skill itself needs only the operator's local report.

## Limits And Review

No live provider, real contributor, market sample, product test or business outcome was verified. Hash checks establish fixture consistency, not truth. One manual hostile-input exercise is not a prompt-injection guarantee across agents.

[The stable review manifest](review-manifest.txt) now lists six repo documentation/skill files, including README and the retained exact integration snippet. The initial skill pass left README integration and independent approval pending; that historical state is superseded by the record below.

## Approved Integration

On 2026-10-05, the user reports that all three independent reviewers APPROVE the five frozen skills/README sections under the lightweight showcase standard (user-reported). Reviewer artifact paths were not supplied. Reviewed input: `/tmp/opencode/five-repo-skill-review-20261005.json`, SHA-256 `0bc5f74f49b71eda3898ad4a0229612e06841a5acd7e599006a77fc8f2b353e2`. The original manifest is retained as review history, not overwritten.

The exact approved snippet is now inserted into README. The GitHub target is `yaronbeen/bright-data-reviews-into-fixes`; package, CLI, module and local paths are unchanged. The README retains the independent-showcase/non-endorsement disclaimer. Skill instructions and the checked example are byte-identical to the reviewed snapshot; no outputs or features were expanded.

Integration validation uses only simple front matter, local links, cited-sample checks and one offline demo replay. The three generated artifacts match the existing goldens; the demo reports zero requests. No new TDD matrix, framework, source/test/package/configuration/core VERIFICATION change, staging, commit, push, remote operation or global installation is part of this pass. Final four-repo documentation hashes, exact intended diffs and the staging list are recorded separately at `/tmp/opencode/four-repo-skills-final-20261005.json`.

Approval concerns the lightweight showcase artifacts, not live Bright Data behavior, real customer findings, authenticated provider origin, market prevalence or business outcomes. GitHub release of Reviews remains a separate top-level action; this integration does not claim publication.
