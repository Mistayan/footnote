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

## Results (15 November, run `bench/work/gd/run1`)

Crawl (Grounded Docs 3.4.1, its CI recipe): react 219 pages, python 500, fastapi 152, vite 28, tailwindcss 223. Both engines search
this same text. Scores on the 59 queries, their metric code:

| System | nDCG@5 | MRR | Recall@5 | Hit@3 |
|---|---|---|---|---|
| Grounded Docs hybrid (EmbeddingGemma 300M) | **0.635** | **0.676** | **0.689** | **0.780** |
| Grounded Docs full-text | 0.492 | 0.505 | 0.559 | 0.593 |
| Footnote hybrid, one database per library | 0.564 | 0.604 | 0.599 | 0.661 |
| Footnote keyword, one database per library | 0.521 | 0.531 | 0.579 | 0.610 |
| Footnote hybrid, one global database | 0.545 | 0.591 | 0.599 | 0.661 |

- **Primary verdict: worse.** Footnote hybrid minus Grounded Docs hybrid, nDCG@5 −0.071 [−0.148, +0.002]: the lower bound is below
  −0.05, so equivalence is not shown (the interval touches zero, so the gap is not proven either).
- **Global database against one per library:** −0.019 [−0.065, +0.021], no measurable pollution. Documentation can go in one
  database or several without a quality cost on this set; per-source databases stay the choice for updates and sharing.
- Reported: keyword 0.521 against Grounded Docs' full-text 0.492. The gap is in tailwindcss (0.368 against 0.550) and fastapi
  (0.624 against 0.811); Footnote leads on react (0.620 against 0.562), is close on python and vite.
- Index build, Footnote (shipped pair, CPU): 754 s for the five libraries, 739 s for the global database. Query latency not
  measured (not an idle-machine run).

### Exploratory, after the results: hits grouped by page

Diagnosis: Footnote returns passages, and the same page often fills two or three of the five places (`body`, `body`, `body`); the
metric counts each page once, while Grounded Docs assembles its results per page. Re-scored with Footnote's top 20 passages
collapsed to their first 5 distinct pages (`docs_vs_grounded_grouped.py`):

| System | nDCG@5 | MRR | Recall@5 | Hit@3 | vs Grounded Docs hybrid |
|---|---|---|---|---|---|
| Footnote hybrid, grouped | 0.600 | 0.616 | 0.672 | 0.661 | −0.035 [−0.107, +0.036] |
| Footnote keyword, grouped | 0.531 | 0.538 | 0.588 | 0.644 | −0.104 [−0.177, −0.031] |

Grouping halves the gap; equivalence is still not shown. Not a verdict (decided after seeing the data). What it suggests, to be
pre-registered before any re-run: (1) documentation search should return pages, not passages; (2) the remaining gap may be the
embedding model (EmbeddingGemma 300M against the small pair), which a same-model run would isolate.
