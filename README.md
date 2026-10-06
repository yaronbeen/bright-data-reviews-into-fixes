# Reviews Into Fixes

Turn a small set of public reviews into one useful question for your product team to investigate next.

Your agent collects actual review text through [Bright Data](https://brightdata.com), groups concrete complaints separately from feature requests and confusing instructions, and keeps contrary reports visible. You get a next check, not an invented bug diagnosis or roadmap ranking.

## What You Get

- A short complaint, request, and documentation-gap summary with exact quotes.
- One practical investigation question and suggested next check.
- Counterexamples, other candidates, and missing evidence with source links.

## Give This To Your Agent

```text
Use review-next-check for [product/service URL]. Collect up to 20 public
reviews from [review source URLs] through my configured Bright Data tools.
Use [optional product context, known issues, or help-page URL]. Group the
concrete complaints, requests, and confusing instructions. Return one
investigation question and next check, with quotes, counterexamples,
source URLs, capture times, and unknowns. If Bright Data is not connected,
ask me to connect it and stop. Do not create tickets or claim a confirmed bug.
```

Read the [review-next-check skill](skills/review-next-check/SKILL.md).
Connect your agent using the [official Bright Data MCP setup](https://docs.brightdata.com/products/mcp-server/remote/quickstart) or this [short connection guide](docs/technical-guide.md).
