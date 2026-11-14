# Research, 2026-11-13

Four desk studies done by separate research agents (web and paper search, nothing installed), each written before any of its ideas was tested.
They are hypotheses with sources, not results. Results land in `../experiments/RESULTS.md` and `../receipts/`, through the same harness and the same
rules as everything else (dev to choose, heldout to confirm, paired bootstrap, cost next to every gain).

| Report | Question | Leading ideas | Status |
|---|---|---|---|
| [competitors.md](competitors.md) | Which two popular products to run head-to-head, besides ICM | **mem0** 2.2.1 (68.9k stars at research time; raw add, no LLM, Qdrant local, dense candidates re-scored by BM25) and **Cognee** 1.6.8 (33.3k stars at research time; SQLite + LanceDB + graph, chunk index) | Both adapters run end to end. Syntec complete; remaining corpora running sequentially. See [current receipts](../experiments/HEADTOHEAD.md). |
| [lexical-boost.md](lexical-boost.md) | How to improve the lexical stage around Tantivy | multilingual learned sparse (OpenSearch neural sparse, query side model-free) fused with BM25; small CPU reranker on the BM25 top 20; per-chunk language routing; character 4-gram field | queued |
| [fusion-boost.md](fusion-boost.md) | How to improve the fusion of lexical and dense | exact score completion; alpha plateau and leave-one-corpus-out check; separate weights for the two models; query-independent squash | Controls and pooled heldout comparison complete. Alpha 0.60 gains +0.0025, below the pre-registered +0.01 bar; no production change. See [results](../experiments/RESULTS.md). |
| [embedding-boost.md](embedding-boost.md) | Which current small models to test | EmbeddingGemma-300M, Harrier-270m, granite-small-english-r2, arctic-embed-m-v2.0 (latency is the constraint: estimated 3 to 4 times the cost of the current models) | All four published-score reproduction gates pass in `../lab/model_checks.jsonl`. Dev quality sweep is queued after the competitor timings; resident single-query encoding measurements follow the sweep. |

## What the reports agree with in our own earlier results

- RRF loses to convex combination; per-query adaptive weights and pseudo-relevance feedback do not help; BM25 parameter tuning and BM25 variants do not matter
  (Tantivy hard-codes k1 and b, our sweep was done in the Python lab).
- int8 vectors cost nothing; Matryoshka truncation to 256 costs 1 to 2 percent, 128 costs 4 to 8 percent (our E11 found the same order).

## Comparison rules for the head-to-head

- Same datasets and splits through `fetch.load`, same metrics (`metrics.py`), same receipt format (`run.py`), queries clipped to 500 bytes for everyone.
- Each product runs as it ships locally, in its own pinned environment, with no LLM call, and the receipt states what was NOT exercised
  (mem0's LLM extraction, Cognee's graph).
- Storage is reported by part (store, derived index, model files), latency with its scope (in-process call versus resident MCP session).
- Models, chunking and fusion differ between products. These runs compare configured local retrieval paths, not isolated storage engines. A matched LanceDB comparison remains separate work.
- Vendor-published numbers are quoted with their provenance and never mixed with ours.

## Current run and report

The competitor queue has 27 runs: six configurations on Syntec, NFCorpus, SciFact and Alloprof, then Footnote and the two multilingual competitors on `mix-fr-en`.
`run_headtohead.sh` is running; `run_models2.sh` waits for it before starting the dev sweep. `model_latency.py --after-log bench/work/models2.log` waits for that sweep, then measures encoding with one model at a time. Do not start another CPU benchmark alongside them.

After model timings, `run_matched.ps1` runs `confirm_models.py`: only configurations gaining at least 0.01 on both dev corpora of a language group get heldout receipts and paired bootstrap checks. It then runs the matched backends and lexical scale controls, writes result reports, and runs the benchmark tests plus Rust fmt/clippy/tests and `git diff --check`. Failure stops the queue with a nonzero exit. This automates the measurement and verification sequence; it never selects or ships a production default.

The latency run uses the same first 100 sorted dev query IDs per corpus for each of the six models, clips query text to 500 UTF-8 bytes, warms each model, then measures individual encodes without a query cache. Its append-only rows in `../sweeps/model_latency.jsonl` include p50/p95, model files size, dimensions, dataset pins, model locks, source hashes and the machine. These are encoding timings, not full retrieval timings; the quality sweep pre-encodes queries and supplies no per-query encoding cost.

The [matched LanceDB experiment](../experiments/LANCEDB-MATCHED.md) follows those timings. Its four controls retain identical chunks, document IDs and float32-decoded vectors, use one fixed a8m model to remove the model confound, and vary storage, lexical engine and fusion. `run_matched.ps1` is queued on `bench/work/model_latency.log`; output and explicit failure records stay under `bench/work/`. The seven backend tests include native FTS mutations before and after optimization and the read-only export boundary. Judged-corpus runs and the added 100k/1M lexical controls are queued; crash safety and production integration remain separate work.

[Environment snapshots](../environments/README.md) record the installed versions. [Interim paired intervals](../experiments/HEADTOHEAD-INTERVALS.md) accompany the available competitor receipts; the NFCorpus Footnote/mem0 interval includes zero. Those per-comparison intervals are exploratory, without multiple-comparison correction.

Regenerate the report from this run only, without changing any receipt:

```powershell
rtk proxy python -B bench/experiments/headtohead_table.py --since 20261113T070000Z | Set-Content -LiteralPath bench/experiments/HEADTOHEAD.md -Encoding utf8
```

The report lists missing rows and receipt sources. It rejects comparisons with different dataset pins or harness hashes. Syntec alone does not establish a general winner.
