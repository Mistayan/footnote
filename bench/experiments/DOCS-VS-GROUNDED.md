# Technical documentation search: Footnote against Grounded Docs

Written 15 November 2026, before any measurement. Backlog P3, feeds item 14 (documentation ingestion).

## Question

Is Footnote at least equivalent to Grounded Docs (`arabold/docs-mcp-server` 3.4.1, MIT) at finding the right documentation page,
on Grounded Docs' own benchmark?

## Data

- Queries: Grounded Docs' `tests/search-eval/dataset.yaml` (status draft, 59 queries: react 12, python 12, fastapi 12, vite 12,
  tailwindcss 11; graded page URLs 1 to 3; intents api-lookup, conceptual, comparison, troubleshooting). Written by its author and
  audited by agents: home ground for Grounded Docs, whose result assembly was tuned on it.
- Pages: Grounded Docs' own CI recipe (`.github/workflows/eval.yml`): react.dev (300 pages), docs.python.org/3/ (500),
  fastapi.tiangolo.com (200), vitejs.dev/guide/ (200), tailwindcss.com/docs (300). Grounded Docs crawls once; the text of every
  page it stored is exported with its URL and indexed by Footnote, so both engines search identical text.

## Systems

- **Grounded Docs, best local configuration:** hybrid search with the strongest local embedding model it can call through an
  OpenAI-compatible endpoint: EmbeddingGemma 300M Q8_0 (`artifacts/gguf/embeddinggemma-300M-Q8_0.gguf`, passed English in test 5)
  through llama.cpp server, roughly ten times the size of Footnote's small pair. Full-text only is also run. Telemetry off (`DOCS_MCP_TELEMETRY=false`).
- **Footnote, as shipped:** hybrid with the default model pair; keyword only is also run. No setting tuned on these queries.
- Context only, not compared: Grounded Docs' published baselines (OpenAI text-embedding-3-small: nDCG@5 0.699, MRR 0.747, Hit@3
  0.831; Context7: nDCG@5 0.673, MRR 0.695, Hit@3 0.831), recorded on another crawl date.

## Scoring

Their metric code and URL normalisation (`lib/metrics.cjs`, `normalizeUrl()`): top 5 results, each relevant URL counted once.
Footnote returns passages; each maps to its page URL.

## Rule

- **Primary metric:** nDCG@5, Footnote hybrid minus Grounded Docs best local configuration, paired bootstrap over the 59 queries
  (10,000 resamples, seed 20261115).
- **Equivalent:** the 95 % interval's lower bound is above -0.05. **Better:** lower bound above 0. Otherwise **worse**.
- Reported, not judged: MRR, Recall@5, Hit@3, per intent; keyword against full-text; index build time; query latency only on an
  idle machine.
- 59 queries is small: an interval crossing zero means "not distinguishable", never "better".
