# Documentation search: confirmation on fresh questions

Written 16 November 2026, before any system ran on these libraries. Confirms (or not) the diagnostics of
[DOCS-FOLLOWUPS-RESULTS-2026-11-15.md](DOCS-FOLLOWUPS-RESULTS-2026-11-15.md), which reused Grounded Docs' 59 already-seen questions.

## Data

- `bench/datasets/docs-confirm/dataset.yaml` (sha256 `88dad3e8b3d405c743b200e54d7b1008aef624fa99998b643a926491ead5e9e7`):
  40 questions, Pydantic 20 and Svelte 20, intents api-lookup, conceptual, comparison, troubleshooting; graded page URLs
  (3 primary, 2 related), 53 distinct URLs, each checked to answer HTTP 200. Written by Claude from the sites' page lists, without
  running either system. Footnote's side wrote them, the reverse of the earlier set (written by Grounded Docs' author).
- Crawl recipe `bench/datasets/docs-confirm/recipe.json`: pydantic.dev/docs/validation/latest/ and svelte.dev/docs/svelte/,
  200 pages each, no exclusion, same for both systems.

## Systems, frozen

- **Grounded Docs 3.4.1**, hybrid with EmbeddingGemma 300M Q8_0 through llama.cpp, telemetry off (as in DOCS-VS-GROUNDED.md).
- **Footnote**, shipped model pair, hybrid, `--per-source 1` (one result per page, chosen by the earlier diagnostics), its own
  crawler (`footnote crawl`, with this branch's fixes: one file per page, redirect scope).

## Rule

- **Primary, end to end:** Footnote (own crawl, hybrid, `--per-source 1`) minus Grounded Docs (own crawl, hybrid), nDCG@5 with
  Grounded Docs' metric code, paired bootstrap over the 40 questions (10,000 resamples, seed 20261116).
  **Equivalent:** 95 % lower bound above −0.05. **Better:** above 0. Otherwise **worse**.
- **Secondary, same text:** Footnote `--per-source 1` on Grounded Docs' exported pages minus Grounded Docs; same rule.
- **Decision:** if the primary is at least equivalent, the crawler ships and documentation searches default to one result per
  page. Otherwise neither, and the per-library results say what to fix.
- Reported, not judged: Footnote as shipped (no cap), keyword only, EmbeddingGemma same weights with the cap, crawl coverage
  of the judged URLs, per library and intent. Query latency not measured.
- 40 questions is small: an interval crossing zero means not distinguishable, never better.
