# Reviews Into Fixes

Turn Amazon reviews into one clear suggestion for what your product team should investigate next.

Your agent collects a small review sample with [Bright Data](https://brightdata.com), then uses the bundled skill to prepare an evidence-backed memo.

## What You Get

- One suggested next check, with exact review quotes and source links.
- Known-issue matches and contrary reports, so your team can check the context.
- Other candidates and unanswered questions for a product-team discussion.

## Give This To Your Agent

```text
For [Amazon product URL or ASIN], collect up to 20 reviews through my
configured Bright Data scraper or MCP. Use [product context file:
product areas, known issues and proposed checks], then follow
review-next-check. Return one next-check memo with supporting quotes,
contrary reports and other candidates. Keep real source links, dates
and unknowns. If collection is unavailable, ask me for a Bright Data export.
```

Skill: [review-next-check](skills/review-next-check/SKILL.md).

In the [checked example (invented data)](docs/skills/review-next-check-example.md), the memo proposes checking setup step 3 while retaining both "Setup stops at step 3" and "Setup works fine." It suggests an investigation, not a confirmed fix.

[Technical guide](docs/technical-guide.md)
