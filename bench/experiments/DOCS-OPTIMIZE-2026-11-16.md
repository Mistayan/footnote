# Documentation retrieval: optimisation on seen sets, decision on a sealed set

Written 16 November 2026, after DOCS-CONFIRM (worse: −0.119 end to end) and before any change below is built.

## Sets

- **Development (seen):** Grounded Docs' 59 questions (react, python, fastapi, vite, tailwindcss) and docs-confirm's 40
  (pydantic, svelte). Every candidate is tuned and selected here only.
- **Sealed decision set:** `bench/datasets/docs-heldout3/dataset.yaml` (sha256
  `aa54e2119e5543d1fc6c0165d3207906f77baa450a8624b3a2f44e054d1c1b7c`): 40 questions, Hono 20 (llms.txt site) and Flask 20
  (Sphinx HTML, no llms.txt), 52 judged URLs, each checked to answer HTTP 200; recipe `docs-heldout3/recipe.json` (200 pages
  each, `llms-*.txt` copies excluded). Written by Claude before any system ran on these libraries. Run once, at the end.
- **General regression guard:** the shipped held-out benches (Alloprof, mix-fr-en, `shipped-ensemble-mcp`), because chunking
  changes touch every corpus.

## Candidates

Search side (product changes, each measured alone then combined):
- **A. Context header:** each chunk carries its page title and heading path (`Title > H2 > H3`) in the embedded text and the
  keyword heading field, instead of the last heading only.
- **B. Structure-aware sizes:** merge sections shorter than a floor into the next one within the same parent, target about
  1,500 characters, never split a fenced code block.
- **C. Post-crawl cleanup:** drop lines repeated on most pages of one site (navigation, footers, banners) and near-duplicate
  pages before indexing.
- **D. Page assembly:** one result per page (`--per-source 1`) returning the best chunk with its heading path.

Crawler side:
- **E. Adaptive concurrency per host:** start at 2 requests in flight, add one after each run of successes up to 8, halve on
  HTTP 429/503 or timeouts, honour `Retry-After` and robots.txt `Crawl-delay`, and remember the last good level per host.
  Compressed responses (gzip, brotli). No probing beyond what the crawl itself requests.

## Rules

- **Keep a search change** when mean nDCG@5 rises on the pooled development questions (99) and neither development set drops
  by more than 0.01, and the general guard drops by no more than 0.005 nDCG@10 on either corpus.
- **Keep E** when the crawl of the seven development libraries is faster in wall time with no more failed or refused
  requests than sequential, and coverage of judged URLs is unchanged.
- **Final decision, once, on the sealed set:** Footnote (own crawl, all kept changes) minus Grounded Docs 3.4.1 (own crawl,
  hybrid, EmbeddingGemma), nDCG@5, paired bootstrap over 40 questions (10,000 resamples, seed 20261117). Equivalent: lower bound
  above −0.05; better: above 0. If at least equivalent, the crawler ships with the kept changes as defaults.
- Reported, not judged: end-to-end time (crawl plus index) of both systems on the sealed libraries, index size.
