# Documentation crawl: coverage and end-to-end search against Grounded Docs

Written 15 November 2026, before any measurement. Backlog item 14; study: [DOCS-INGESTION-STUDY.md](../../docs/research/DOCS-INGESTION-STUDY.md).
Companion to [DOCS-VS-GROUNDED.md](DOCS-VS-GROUNDED.md) (search on identical text).

## Data

Grounded Docs' `tests/search-eval/dataset.yaml` (59 queries, react, python, fastapi, vite, tailwindcss; graded page URLs) and its
CI crawl recipe: the same start URL and page budget per library (react.dev 300, docs.python.org/3/ 500, fastapi.tiangolo.com 200,
vitejs.dev/guide/ 200, tailwindcss.com/docs 300).

## Systems

- **Grounded Docs 3.4.1:** its own crawler and search, best local configuration (EmbeddingGemma 300M through llama.cpp, as in
  DOCS-VS-GROUNDED.md), telemetry off.
- **Footnote, minimal:** `ureq`, `llms.txt` and sitemap discovery then a breadth-first link crawl in scope, `dom_smoothie`
  main-content extraction, `htmd` Markdown; shipped search (hybrid, default pair); settings frozen before the run.
- **Footnote, spider:** the `spider` crate for discovery and fetching, same extraction and search.

Every crawler fetches each library once; raw responses are cached and replayed to the extraction variants, so the sites are
not fetched again per variant. Politeness: robots.txt, at most 2 requests at a time per host, an identifying user agent.

## Measures

- **B. Coverage:** share of the dataset's relevant URLs (grade 2 or 3, normalised as Grounded Docs does) present in each
  crawl, per library and overall. Pages fetched, bytes, wall time, pages needing JavaScript (empty main content).
- **C. End to end:** nDCG@5 (primary), MRR, Recall@5, Hit@3 with Grounded Docs' metric code, each system searching its own crawl.

## Rule

- **Footnote's crawler is adopted** (the minimal one unless the spider variant beats it on coverage by at least 5 points of
  relevant URLs) when its end-to-end nDCG@5 minus Grounded Docs' has a paired bootstrap 95 % interval (59 queries, 10,000
  resamples, seed 20261115) with lower bound above -0.05: at least equivalent. Above 0: better.
- **Otherwise:** the per-library coverage and the queries lost say whether discovery, extraction or search is at fault; no
  crawler ships until that part is fixed and re-measured on a new run.
- 59 queries written by the competitor's author: an interval crossing zero means not distinguishable, never better.
- Reported, not judged: speed, bytes, pages needing JavaScript; latency only on an idle machine.
