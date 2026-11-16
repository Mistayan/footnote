# Documentation retrieval follow-up results

15 November 2026. Protocol: [DOCS-FOLLOWUPS-2026-11-15.md](DOCS-FOLLOWUPS-2026-11-15.md).
These 59 questions and the earlier Grounded Docs results were already observed.
The follow-ups are diagnostics, not independent confirmation and do not replace
the original verdict in [DOCS-VS-GROUNDED.md](DOCS-VS-GROUNDED.md).

## Native cap: same Grounded Docs page exports

The product already supports `--per-source 1`: no new ranking code was needed.
Two complete runs for each mode returned identical URL rankings. Inputs and
raw rankings are retained under `bench/work/gd/page-cap-20261115/inputs.json`
and `*-pass{1,2}.json`; the full per-query analysis is in `results.json` there.
The cap is per indexed file, which corresponds to a page in this export. It is
not a general guarantee of deduplication by normalized URL.

| Condition | nDCG@5 | Recall@5 | Hit@3 | nDCG difference vs Grounded Docs hybrid, paired 95% CI |
|---|---:|---:|---:|---:|
| Grounded Docs hybrid, existing run | 0.635 | 0.689 | 0.780 | reference |
| Footnote hybrid, original top 5 | 0.564 | 0.599 | 0.661 | -0.071 [-0.148, +0.002] |
| Footnote hybrid, old top 20 grouped afterward | 0.600 | 0.672 | 0.661 | -0.035 [-0.107, +0.035] |
| Footnote hybrid, `--per-source 1` | 0.608 | 0.689 | 0.678 | -0.027 [-0.100, +0.046] |
| Footnote lexical, `--per-source 1` | 0.539 | 0.605 | 0.661 | -0.096 [-0.171, -0.020] |

The native cap improves the observed hybrid score on the same questions, but
the interval does not satisfy the earlier -0.05 non-inferiority margin. The
decision to test the cap was made after looking at this dataset, so a new,
independently judged question set is needed for a confirmatory claim.

## Preliminary crawler coverage

Each number counts distinct normalized relevant URLs of grade 2 or 3 in the
competitor's 59-query set, separately by library. Both tested crawlers fetched
the public sites independently. Spider 2.53.9 used its own isolated benchmark
binary, robots checking, a page limit, 2 concurrent requests and a 100 ms
delay. Its configuration was checked against a local robots/scope/budget
fixture before the public crawl.

| Library | Relevant URLs | Minimal | Spider | Grounded Docs, earlier crawl |
|---|---:|---:|---:|---:|
| React | 16 | 16 | 16 | 16 |
| Python | 15 | 15 | 13 | 15 |
| FastAPI | 15 | 15 | 15 | 15 |
| Vite | 12 | 10 | 10 | 10 |
| Tailwind | 13 | 11 | 11 | 11 |
| **Total** | **71** | **67** | **65** | **67** |

The minimal crawler's 300 React files correspond to 203 unique URLs after the
metric's normalization; `.md` and non-`.md` variants can occupy separate
files. Spider's limit counts pages returned by Spider, while minimal stops
after successfully writing its requested number of pages. Consequently these
are not matched successful-page budgets. The earlier protocol also proposed
reusing raw HTTP responses across variants, but the current runners do not do
that. Neither coverage result alone establishes crawler quality or license to
ship. Raw URL manifests, coverage JSON and logs are in
`bench/work/crawl/minimal/` and `bench/work/crawl/spider-20261115/`; the
previous failed attempt remains in `bench/work/crawl/minimal-coverage.out`.

## Preliminary end to end on independent crawls

Both result rankings were repeated and matched. The minimal crawler's five
databases were checked for one vector per indexed chunk and model. Source
input hashes and raw results are in `bench/work/crawl/minimal/`.

| Condition | nDCG@5 | Recall@5 | Hit@3 | nDCG difference vs Grounded Docs hybrid, paired 95% CI |
|---|---:|---:|---:|---:|
| Grounded Docs, earlier crawl and hybrid search | 0.635 | 0.689 | 0.780 | reference |
| Minimal crawl, Footnote hybrid, top 5 | 0.548 | 0.607 | 0.678 | -0.087 [-0.158, -0.016] |
| Minimal crawl, Footnote hybrid, `--per-source 1` | 0.589 | 0.684 | 0.712 | -0.046 [-0.117, +0.025] |
| Minimal crawl, top 20 grouped by normalized URL | 0.605 | 0.701 | 0.695 | -0.030 [-0.099, +0.037] |

The baseline misses the -0.05 lower-bound criterion. The per-file cap is an
adaptive diagnostic, and also misses it. In the capped run, 24 of 59 searches
still contain duplicate normalized URLs because the crawler stored multiple
files for the same normalized page. The capped runs and input hashes are in
`bench/work/crawl/minimal-cap-20261115/`. The raw-fetch replay and budget
limitations above still apply; these are not fresh held-out quality claims.
An additional client-side diagnostic grouped the first 20 chunks by normalized
URL and returned up to five pages. It improved the observed score but still
missed the earlier margin; a 20-chunk candidate cap can also omit a relevant
page. Evidence: `bench/work/crawl/minimal-url-group-20261115/`. The source
files remain distinct, and this diagnostic has not changed the shipped search
behavior.

## Same EmbeddingGemma weights, exported Grounded Docs pages

Completed 15 November. Footnote reindexed the five previously exported Grounded
Docs corpora with the same EmbeddingGemma-300M Q8_0 GGUF weights and used
`--per-source 1`. For 59 previously used queries, nDCG@5 was **0.65356**
against Grounded Docs' **0.63499**: paired difference **+0.01857**, bootstrap
95% interval **[-0.03575, +0.07326]**. Recall@5 was 0.74576; both Footnote
ranking passes were identical. The interval includes zero. Its lower bound is
above -0.05, but this is an adaptive diagnostic on reused questions and is not
an independent confirmation of the earlier equivalence rule.

Only model weights and source pages were matched: chunking and indexing,
tokenization, truncation, fusion, result assembly and CPU/GPU runtime still
differ. No effect can be assigned to weights or ranking alone. Source hashes,
model profile, database build receipts and both passes are preserved in
`bench/work/gd/same-weights-20261115/`.
